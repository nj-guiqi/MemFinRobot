set DASHSCOPE_API_KEY=sk-ced3f855f17240dc9c9c199e6b39c53b

call python eval/scripts/run_eval_mem0.py ^
        --dataset eval/datasets/MemFinConv_24.jsonl ^
        --workers-dialog 4 --run-id 20260220_155804
