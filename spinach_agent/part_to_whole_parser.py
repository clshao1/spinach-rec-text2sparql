import json
import sys

from typing import List, Dict
from chainlite import chain, get_logger, llm_generation_chain, pprint_chain
from langgraph.graph import END, StateGraph
from langchain_core.runnables import RunnablePassthrough


from spinach_agent.parser_state import (
    Action,
    PartToWholeParserState,
    SparqlQuery,
    state_to_dict,
    state_to_string,
)
from spinach_agent.parser_utils import (
    BaseParser,
    execute_sparql_object,
    get_prune_edges_chain,
    parse_string_to_json,
    sparql_string_to_sparql_object,
)
from wikidata_utils import (
    SparqlExecutionStatus,
    get_outgoing_edges,
    search_span,
)
from wikidata_utils import get_property_examples

logger = get_logger(__name__)

wikidata_data_type_to_description_map = {
    # "string": "",
    "external-id": "Represents an identifier used in an external system.",
    "url": "Represents a link to an external resource or site. Can be converted to string using STR()",
    "commonsMedia": "References to files (like images, audio) on Wikimedia Commons.",
    "geo-shape": "Reference to map data files on Wikimedia Commons.",
    "tabular-data": "Reference to tabular data files on Wikimedia Commons.",
    "math": "Stores and displays formatted mathematical formulas.",
    "musical-notation": "Stores and displays musical scores as generated images in .png format.",
}


def format_wikidata_search_result(arr):
    ret = []
    for item in arr:
        label = item.get(
            "label", ""
        )  # Get the label or an empty string if not available
        id = item.get("id", "")  # Get the id or an empty string if not available
        description = item.get(
            "description", ""
        )  # Get the description or an empty string if not available

        display_string = f"{label} ({id}): {description}"
        if "datatype" in item:
            data_type = item["datatype"]
            if data_type in wikidata_data_type_to_description_map:
                data_type += f" ({wikidata_data_type_to_description_map[data_type]})"
            display_string += f"\tData Type: {data_type}"

        ret.append(display_string)
    return "\n".join(ret)


@chain
async def json_to_string(j: dict) -> str:
    return json.dumps(j, indent=2, ensure_ascii=False)


@chain
async def json_to_action(action_dict: dict) -> Action:
    thought = action_dict["thought"]
    action_name = action_dict["action_name"]
    action_argument = action_dict["action_argument"]

    if action_name == "execute_sparql":
        assert action_argument, action_dict

    return Action(
        thought=thought,
        action_name=action_name,
        action_argument=action_argument,
    )


# async def sparql_debugger_router(state):
#     # last action was an execute_sparql()
#     current_action = PartToWholeParser.get_current_action(state)
#     assert current_action.action_name == "execute_sparql"
#     sparql_to_debug = state["generated_sparqls"][-1]
#     sparqls_to_help_debug = []
#     # TODO feed in previous observations of PIDs and QIDs and entity pages as well
#     if not sparql_to_debug.has_results():
#         print("sparql_to_debug = ", sparql_to_debug)
#         for _ in range(15):
#             o = await PartToWholeParser.debug_sparql_chain.ainvoke(
#                 {
#                     "sparql_to_debug": sparql_to_debug,
#                     "sparqls_to_help_debug": sparqls_to_help_debug,
#                 }
#             )
#             print("sparql to help debug =  ", o)
#             print("execution result:", o.execution_result)
#             sys.stdout.flush()
#             sparqls_to_help_debug.append(o)
#         exit()
#     return "controller"

def display_actions(actions):
    # truncate actions
    actions = actions[-10:]
    
    action_history = []
    for i, a in enumerate(actions):
        include_observation = True
        if i < len(actions) - 2 and a.action_name in [
            "get_wikidata_entry",
            "search_wikidata",
        ]:
            include_observation = False
        if a.action_name == "stop":
            include_observation = False
        action_history.append(a.to_jinja_string(include_observation))
    return action_history


class PartToWholeParser(BaseParser):
    MAX_RECURSIVE_DEPTH = 1  # Maximum recursion depth
    
    @classmethod
    def initialize(
        cls,
        engine: str,
    ):
        @chain
        async def initialize_state(input):
            return PartToWholeParserState(
                question=input["question"],
                conversation_history=input["conversation_history"],
                engine=engine,
                action_counter=0,
                actions=[],
                response="",
                recursive_depth=input.get("recursive_depth", 0),  # Use provided depth or default to 0
                decomposition_result=None,
                simple_subquery_result=None,
                complex_subquery_result=None,
                is_processing_simple_subquery=False,
                is_processing_complex_subquery=False,
                merge_operation=None,
                original_question=None,
                simple_subquery_actions=[],
                # generated_sparqls=[],
            )

        # build the graph
        graph = StateGraph(PartToWholeParserState)
        graph.add_node("start", lambda x: {})
        graph.add_node("controller", PartToWholeParser.controller)
        graph.add_node("execute_sparql", PartToWholeParser.execute_sparql)
        graph.add_node("get_wikidata_entry", PartToWholeParser.get_wikidata_entry)
        graph.add_node(
            "search_wikidata",
            PartToWholeParser.search_wikidata,
        )
        graph.add_node("get_property_examples", PartToWholeParser.get_property_examples)
        graph.add_node("decompose", PartToWholeParser.decompose)
        graph.add_node("merge_results", PartToWholeParser.merge_results)
        graph.add_node("max_depth_handler", PartToWholeParser.max_depth_handler)
        graph.add_node("reporter", PartToWholeParser.reporter)
        graph.add_node("stop", PartToWholeParser.stop)

        graph.set_entry_point("start")

        graph.add_edge("start", "controller")
        graph.add_conditional_edges(
            "controller",
            PartToWholeParser.router,  # the function that will determine which node is called next.
        )
        for n in [
            "execute_sparql",
            "get_wikidata_entry",
            "search_wikidata",
            "get_property_examples",
            "decompose",
        ]:
            graph.add_edge(n, "controller")
        graph.add_conditional_edges(
            "stop",
            PartToWholeParser.stop_router,
        )
        graph.add_edge("max_depth_handler", "stop")
        graph.add_edge("merge_results", "reporter")
        graph.add_edge("reporter", END)

        # graph.add_edge("execute_sparql", sparql_debugger_router)

        cls.controller_chain = (
            {
                "input": llm_generation_chain(
                    template_file="controller.prompt",
                    engine=engine,
                    max_tokens=700,
                    temperature=1.0,
                    top_p=0.9,
                    # stop_tokens=["Observation:"],
                    keep_indentation=True,
                )
            }
            | llm_generation_chain(
                template_file="format_actions.prompt",
                engine=engine,
                max_tokens=700,
                keep_indentation=True,
                output_json=True
            )
            | parse_string_to_json
            | json_to_action
        )

        cls.sparql_chain = sparql_string_to_sparql_object | execute_sparql_object
        cls.prune_edges_chain = get_prune_edges_chain(engine=engine) | json_to_string
        cls.reporter_chain = llm_generation_chain(
            template_file="conversation_reporter.prompt",
            engine=engine,
            max_tokens=2000,
            temperature=0.0,
            keep_indentation=True,
        )
        cls.language_detection_chain = llm_generation_chain(
                    template_file="language_detection.prompt",
                    engine=engine,
                    max_tokens=50,
                    temperature=0.0,
                    top_p=0.9,
                    keep_indentation=True,
                )
        
        cls.decompose_chain = (
            llm_generation_chain(
                template_file="decompose.prompt",
                engine=engine,
                max_tokens=400,
                temperature=0.2,
                keep_indentation=True,
                output_json=True
            )
            | parse_string_to_json  # Returns dict directly
        )

        # cls.debug_sparql_chain = (
        #     llm_generation_chain(
        #         template_file="sparql_debugger.prompt", engine=engine, max_tokens=1000
        #     )
        #     | extract_code_block_from_output.bind(code_block="sparql")
        #     | cls.sparql_chain
        # )

        compiled_graph = graph.compile()
        cls.runnable = initialize_state | compiled_graph
        logger.info("Finished initializing the graph.")
        # compiled_graph.get_graph().print_ascii()
        # sys.stdout.flush()

    @staticmethod
    def get_current_action(state):
        return state["actions"][-1]

    @staticmethod
    async def router(state):
        move_back_on_duplicate_action = 2
        
        # Check recursive depth limit first (prevent infinite recursion)
        current_depth = state.get("recursive_depth", 0)
        if current_depth >= PartToWholeParser.MAX_RECURSIVE_DEPTH:
            # If we have actions and already stopping, continue to stop
            if len(state.get("actions", [])) > 0:
                current_action = PartToWholeParser.get_current_action(state)
                if current_action.action_name == "stop":
                    return "stop"
            # Otherwise, route to max_depth_handler to create stop action
            logger.warning("Maximum recursive depth %d reached in router, routing to stop", PartToWholeParser.MAX_RECURSIVE_DEPTH)
            return "max_depth_handler"
        
        # Get current action (should exist at this point)
        current_action = PartToWholeParser.get_current_action(state)
        
        # After decompose, continue with controller (decompose handler already processed both subqueries)
        if current_action.action_name == "decompose" and state.get("decomposition_result"):
            return "controller"
        
        # If stop action, always route to stop (it will handle complex subquery routing via stop_router)
        if current_action.action_name == "stop":
            return "stop"
        
        # If we're processing complex subquery, continue with controller
        if state.get("is_processing_complex_subquery", False):
            return "controller"
        
        if current_action in state["actions"][-5:-1]:
            logger.warning(
                "Took duplicate action %s, going back %d steps.",
                current_action.action_name,
                move_back_on_duplicate_action,
            )
            # Remove generated_sparqls as well
            if len(state["actions"]) - 2 >= 0:
                for i in range(len(state["actions"]) - 2, -1, -1):
                    if state["actions"][i].action_name == "execute_sparql":
                        state["generated_sparqls"] = state["generated_sparqls"][:-1]
            state["actions"] = state["actions"][:-move_back_on_duplicate_action]
            state["action_counter"] -= move_back_on_duplicate_action
            return "controller"

        if state["action_counter"] >= 15:
            return "reporter"
        
        return state["actions"][-1].action_name

    @staticmethod
    @chain
    async def controller(state):
        current_depth = state.get("recursive_depth", 0)
        logger.info("Running for question %s with depth %d", state["question"], current_depth)

        # make the history shorter
        actions = state["actions"]
        action_history = display_actions(actions)

        logger.info("Invoking controller chain with depth %d", current_depth)
        action = await PartToWholeParser.controller_chain.ainvoke(
            {
                "conversation_history": state["conversation_history"],
                "question": state["question"],
                "action_history": action_history
            }
        )
        logger.info("Finishing controller chain with depth %d", current_depth)
        return {"actions": action, "action_counter": 1}

    @staticmethod
    @chain
    async def execute_sparql(state):
        current_action = PartToWholeParser.get_current_action(state)
        assert current_action.action_name == "execute_sparql"
        # print("executing ", current_action.action_argument)
        sparql = PartToWholeParser.sparql_chain.invoke(
            current_action.action_argument
        )
        current_action.action_argument = (
            sparql.sparql
        )  # update it with the cleaned and optimized SPARQL
        if sparql.has_results():
            current_action.observation = sparql.results_in_table_format()
            current_action.observation_markdown = sparql.results_in_markdown_format()
            # print("SPARQL execution result:", current_action.observation)
        else:
            if sparql.execution_status == SparqlExecutionStatus.SYNTAX_ERROR:
                msg = sparql.execution_status.get_message()
                current_action.observation = "Query had syntax error." if not msg else msg
            elif sparql.execution_status == SparqlExecutionStatus.TIMED_OUT:
                current_action.observation = "Query execution timed out."
            elif sparql.execution_status == SparqlExecutionStatus.OTHER_ERROR:
                current_action.observation = "Query execution ran into an error."
            else:
                current_action.observation = "Query returned empty result."

        return {"generated_sparqls": sparql}

    @staticmethod
    @chain
    async def get_wikidata_entry(state):
        current_action = PartToWholeParser.get_current_action(state)
        assert current_action.action_name == "get_wikidata_entry"
        wikidata_entry = get_outgoing_edges(
            current_action.action_argument, compact=True
        )
        # NOTE: The only seen exception from this so far
        # is due to contex too long
        try:
            action_result = await PartToWholeParser.prune_edges_chain.ainvoke(
                {
                    "question": state["question"],
                    "conversation_history": state["conversation_history"],
                    "outgoing_edges": json.dumps(
                        wikidata_entry, indent=2, ensure_ascii=False
                    ),
                    "entity_and_description": current_action.action_argument,
                }
            )
        except Exception:
            action_result = ""
        current_action.observation = action_result

    @staticmethod
    @chain
    async def search_wikidata(state):
        current_action = PartToWholeParser.get_current_action(state)
        assert current_action.action_name == "search_wikidata"
        action_results = search_span(
            current_action.action_argument,
            limit=8,
            return_full_results=True,
            type="item",
        )
        action_results += search_span(
            current_action.action_argument,
            limit=4,
            return_full_results=True,
            type="property",
        )
        current_action.observation = format_wikidata_search_result(action_results)

    @staticmethod
    @chain
    async def get_property_examples(state):
        current_action = PartToWholeParser.get_current_action(state)
        assert current_action.action_name == "get_property_examples"
        examples = get_property_examples(current_action.action_argument)
        action_result = []
        try:
            for e in examples:
                action_result.append(f"{e[0]} -- {e[1]} --> {e[2]}")
        except:
            logger.exception(e)
        current_action.observation = "\n".join(action_result)

    @staticmethod
    @chain
    async def stop(state):
        current_action = PartToWholeParser.get_current_action(state)
        assert current_action.action_name == "stop"
        
        # If we're processing complex subquery, handle it even without valid SPARQL
        if state.get("is_processing_complex_subquery", False):
            original_question = state.get("original_question", state["question"])
            # Check if we have a valid SPARQL result
            if (
                len(state.get("generated_sparqls", [])) > 0
                and state["generated_sparqls"][-1].has_results()
            ):
                final_sparql = state["generated_sparqls"][-1]
                if final_sparql.sparql.strip().endswith("LIMIT 10"):
                    logger.info("Removing LIMIT 10 from the final SPARQL")
                    s = final_sparql.sparql.strip()[:-len("LIMIT 10")]
                    final_sparql = SparqlQuery(sparql=s)
                    final_sparql.execute()
                complex_result = final_sparql
            else:
                logger.warning("Complex subquery did not produce valid SPARQL, storing None")
                complex_result = None
            
            return {
                "complex_subquery_result": complex_result,
                "question": original_question,  # Restore original question
            }
        
        # Normal stop handling (not processing complex subquery)
        for s in state["generated_sparqls"]:
            assert isinstance(s, SparqlQuery)
        if (
            len(state["generated_sparqls"]) == 0
            or not state["generated_sparqls"][-1].has_results()
        ):
            logger.warning("Stop() was called without a good SPARQL. Starting over.")
            state["generated_sparqls"] = []
            state["actions"] = []
            state["action_counter"] = 0
            return

        logger.info("Finished run for question %s", state["question"])
        final_sparql = state["generated_sparqls"][-1]
        if final_sparql.sparql.strip().endswith("LIMIT 10"):
            logger.info("Removing LIMIT 10 from the final SPARQL")
            s = final_sparql.sparql.strip()[:-len("LIMIT 10")]
            final_sparql = SparqlQuery(sparql=s)
            final_sparql.execute()
        
        return {"final_sparql": final_sparql}

    @staticmethod
    @chain
    async def reporter(state):
        actions = state["actions"]
        action_history = []
        for i, a in enumerate(actions):
            include_observation = True
            if i < len(actions) - 2 and a.action_name in [
                "get_wikidata_entry",
                "search_wikidata",
            ]:
                include_observation = False
            elif a.action_name == "stop":
                include_observation = False
            action_history.append(a.to_jinja_string(include_observation))
        
        language = await PartToWholeParser.language_detection_chain.ainvoke(
            {
                "question": state["question"],
            }
        )
        
        response = await PartToWholeParser.reporter_chain.ainvoke(
            {
                "language": language,
                "question": state["question"],
                "conversation_history": state["conversation_history"],
                "action_history": action_history
            }
        )
        state["response"] = response
        return {"response": response}
    
    @staticmethod
    @chain
    async def decompose(state):
        current_action = PartToWholeParser.get_current_action(state)
        assert current_action.action_name == "decompose"

        logger.info("Initializing decompose step at depth %d", state.get("recursive_depth", 0))

        logger.info("Invoking decompose chain at depth %d", state.get("recursive_depth", 0))
        decomposition = await PartToWholeParser.decompose_chain.ainvoke(
            {
                "question": state["question"],
                "conversation_history": state["conversation_history"],
                "goal": current_action.action_argument,
            }
        )
        logger.info("Finishing decompose chain at depth %d", state.get("recursive_depth", 0))

        # Store decomposition result
        current_action.observation = json.dumps(decomposition, indent=2, ensure_ascii=False)
        
        simple_subquery = decomposition.get("simple_subquery", "")
        complex_subquery = decomposition.get("complex_subquery", "")
        merge_operation = decomposition.get("merge_operation", "")
        
        logger.info("Simple subquery: %s", simple_subquery)
        logger.info("Complex subquery: %s", complex_subquery)
        
        # Process simple subquery: Launch a new PartToWholeParser instance recursively
        simple_result = None
        simple_subquery_actions = []
        recursive_depth_for_simple = state.get("recursive_depth", 0) + 1
        try:
            logger.info("Processing simple subquery at depth %d: %s", recursive_depth_for_simple, simple_subquery)
            recursive_input = {
                "question": simple_subquery,
                "conversation_history": state.get("conversation_history", []),
                "recursive_depth": recursive_depth_for_simple,
            }
            logger.info("Invoking recursive parser with depth %d", recursive_depth_for_simple)
            recursive_result = await PartToWholeParser.runnable.ainvoke(recursive_input)
            logger.info("Recursive parser completed. Result keys: %s", list(recursive_result.keys()) if recursive_result else "None")
            simple_result = recursive_result.get("final_sparql")
            # Capture actions from the recursive parser
            simple_subquery_actions = recursive_result.get("actions", [])
            
            if simple_result and simple_result.has_results():
                logger.info("Simple subquery completed successfully with %d actions", len(simple_subquery_actions))
            else:
                logger.warning("Simple subquery did not produce valid results. Result: %s", simple_result)
        except Exception as e:
            logger.exception("Error processing simple subquery: %s", e)
        
        # Process complex subquery: Update state to use complex subquery as new question
        # and continue with the current ReAct loop
        original_question = state.get("question", "")
        logger.info("Updating question to complex subquery for ReAct loop continuation")
        
        # Preserve existing actions (including the decompose action) and append simple subquery actions
        # so they all appear in the log. We need to modify state directly since the reducer appends items.
        current_actions = list(state.get("actions", []))
        # The decompose action is already in current_actions, so we append simple subquery actions
        updated_actions = current_actions + simple_subquery_actions
        # Directly update the state's actions list so they appear in the log
        state["actions"] = updated_actions
        
        # Update state with decomposition and results
        return {
            "decomposition_result": decomposition,
            "merge_operation": merge_operation,
            "recursive_depth": state.get("recursive_depth", 0) + 1,
            "simple_subquery_result": simple_result,
            "simple_subquery_actions": simple_subquery_actions,  # Store actions from recursive processing
            "question": complex_subquery,  # Update question to complex subquery
            "is_processing_complex_subquery": True,
            "original_question": original_question,  # Store original for later restoration
            "action_counter": len(updated_actions),  # Update counter to reflect all actions so far
        }

    @staticmethod
    @chain
    async def merge_results(state):
        """Merge results from simple and complex subqueries"""
        simple_result = state.get("simple_subquery_result")
        complex_result = state.get("complex_subquery_result")
        merge_operation = state.get("merge_operation", "")
        
        logger.info("Merging results at depth %d", state.get("recursive_depth", 0))
        logger.info("Simple result: %s", simple_result)
        logger.info("Complex result: %s", complex_result)
        logger.info("Merge operation: %s", merge_operation)
        
        # For now, we'll use the complex result if available, otherwise simple result
        # In a more sophisticated implementation, we'd parse the merge_operation
        # and generate a SPARQL query that combines both results
        if complex_result and complex_result.has_results():
            merged_sparql = complex_result
        elif simple_result and simple_result.has_results():
            merged_sparql = simple_result
        else:
            logger.warning("No valid results to merge")
            # Create an empty result
            merged_sparql = SparqlQuery(sparql="SELECT ?x WHERE { ?x ?y ?z } LIMIT 0")
            merged_sparql.execute()
        
        # Store the merged result
        return {
            "generated_sparqls": merged_sparql,
            "is_processing_simple_subquery": False,
            "is_processing_complex_subquery": False,
        }

    @staticmethod
    @chain
    async def max_depth_handler(state):
        """Handle max depth reached by creating a stop action"""
        logger.warning("Creating stop action due to max depth %d reached", PartToWholeParser.MAX_RECURSIVE_DEPTH)
        return {
            "actions": Action(
                thought=f"Maximum recursive depth {PartToWholeParser.MAX_RECURSIVE_DEPTH} reached. Stopping decomposition.",
                action_name="stop",
                action_argument=""
            ),
            "action_counter": 1
        }

    @staticmethod
    async def stop_router(state):
        """Route after stop action"""
        # If we're processing complex subquery, go to merge_results
        if state.get("is_processing_complex_subquery", False):
            return "merge_results"
        # Otherwise, go to reporter as normal
        return "reporter"