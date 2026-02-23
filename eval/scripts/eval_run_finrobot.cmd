set FINNHUB_API_KEY=
set DASHSCOPE_API_KEY=

call python eval/scripts/run_eval_finrobot.py ^
        --dataset eval/datasets/MemFinConv_24.jsonl ^
        --workers-dialog 4 ^
        --workers-judge 4 ^
        --agent-config Market_Analyst ^
        --temperature 0.7 ^
        --chat-model qwen3.5-plus ^


