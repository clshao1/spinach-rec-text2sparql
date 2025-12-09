<p align="center">
    <h1 align="center">
        <b>Recursive Decomposition for SPINACH: A Text-to-SPARQL Semantic Parsing Extension</b>
    </h1>
</p>

<p align="center">
    Full Github:
    <a href="https://github.com/clshao1/spinach-rec-text2sparql/tree/claire" target="_blank">
        https://github.com/clshao1/spinach-rec-text2sparql/tree/claire
    </a>
    <br>
</p>

# About

This repository extends the original SPINACH agent with a recursive decomposition and merge mechanism for handling complex, multi-constraint SPARQL queries. Our approach introduces new `decompose` and `merge` actions inside the ReAct-based controller, enabling the agent to split difficult questions into smaller subqueries, solve them independently, and recombine results into a final SPARQL program.

For more details on the original SPINACH agent and datasets, check out [the SPINACH Github](https://github.com/stanford-oval/spinach).

# Folder Structure
`datasets/` contains all prior dataset files. Predictions for our modified SPINACH agent used in the paper can be found at:
- `spinach_dataset/` for SPINACH
- `datasets/qald_10/en/` for QALD-10 full set
Due to compute reasons, we needed to run prediction and evalauation on some of the datasets using sub-samples (smaller batch sizes), so some of the evaluation results may be broken up into multiple output and log files.

`spinach_agent/` contains implementation of the modified, recursive decomposition SPINACH agent.

`spinach_agent/prompts/` contains all of the prompts used for LLM response generation.

`datasets/` and `spinach_dataset/` contains all of our datasets and evaluation results. In particular, we benchmarked on QALD-10 and the SPINACH dataset.

`tests/` contains all tests, which use `pytest`. You can run all tests by running `invoke tests`. `test_eval.py`, which stores test cases for the row-major F1 implementation, can be run via `python tests/test_eval.py`.

# Running the SPINACH agent and evaluating results
Since we extended our implementation off of the original SPINACH agent, the below set-up is borrowed from the original SPINACH agent.

## Set up environment

Run `conda env create -f conda_env.yaml`.

Create a file called `API_KEYS` and write various API keys inside. The format is one key per line, for example `OPENAI_API_KEY=sk-...`

## Run SPINACH parser and evaluate

```
inv evaluate-parser --parser-type part_to_whole --subsample=-1 --engine=gpt-4o --dataset=datasets/qald_10/en/test.json --output-file=datasets/qald_10/en/spinach_output_test.json --regex-use-select-distinct-and-id-not-label --llm-extract-prediction-if-null
```

The two flags at the end are for:

- `llm-extract-prediction-if-null`: If a reasoning chain ended without any predicted SPARQL, asks a LLM to return a SPARQL. This part is implemented inside `extract_sparql.ainvoke`. This is helpful because for simple queries, LLMs could just use ``get_wikidata_entry'' to get results instead of ever writing a SPARQL. We enabled this flag for all datasets we evaluated on.
- `--regex-use-select-distinct-and-id-not-label`: Attempts to use regex to force use `SELECT DISTINCT` instead of `SELECT`, and try to always include the variable QID instead of the label (i.e., use `x` instead of `xLabel`). We enabled this for all datasets except the new SPINACH dataset that we evaluated on (The SPINACH dataset involves more complex predicted SPARQLs. The regex is not sophisticated enough to handle these cases.)

The script will also write a `.log` file with SPINACH's chain of reasonings and actions with the same file name as the `.json` output.

You can re-evaluate the output simply from the `.json` file:
```
python spinach_agent/evaluate_file.py --input datasets/qald_10/en/spinach_output_test.json
```

If you'd like to simply run the parser on a list of questions, use the following code from `evaluate_parser.py`:
```python
from spinach_agent.part_to_whole_parser import PartToWholeParser

semantic_parser_class = PartToWholeParser
semantic_parser_class.initialize(engine=args.engine) # e.g. "gpt-4o"

chain_output = semantic_parser_class.run_batch(
    questions, # this should be a dict of {"question": "...", "conversation_history": [...]}, conversation_history can be empty list if running on single-turn questions
)
```