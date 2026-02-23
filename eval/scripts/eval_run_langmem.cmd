set DASHSCOPE_API_KEY=your_dashscope_api_key

call python eval/scripts/run_eval_langmem.py ^
        --dataset eval/datasets/MemFinConv_24.jsonl ^
        --workers-dialog 4 ^
        --workers-judge 1 ^
        --chat-model qwen3.5-plus ^
        --embedding-model text-embedding-v4

