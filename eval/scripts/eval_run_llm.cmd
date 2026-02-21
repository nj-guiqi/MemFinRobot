set DASHSCOPE_API_KEY=

call python eval/scripts/run_eval_llm.py ^
        --dataset eval/datasets/MemFinConv_24.jsonl ^
        --workers-dialog 4 --workers-judge 4



