set FINNHUB_API_KEY=d6d8oapr01qgk7ml0ukgd6d8oapr01qgk7ml0ul0
set DASHSCOPE_API_KEY=sk-ced3f855f17240dc9c9c199e6b39c53b

call python eval/scripts/run_eval_finrobot.py ^
        --dataset eval/datasets/MemFinConv_24.jsonl ^
        --workers-dialog 4 ^
        --workers-judge 4 ^
        --agent-config Market_Analyst ^
        --temperature 0.7 ^
        --chat-model qwen3.5-plus ^


