set DASHSCOPE_API_KEY=

call python eval/scripts/run_eval_mem0.py ^
        --dataset eval/datasets/MemFinConv_24.jsonl ^
        --workers-dialog 4 --run-id 20260220_155804
