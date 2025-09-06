from datetime import datetime

from langchain_core.callbacks import BaseCallbackHandler

BUFFER_TOKENS = 100

MODEL_PRICING = {
    "anthropic.claude-3-7-sonnet-20250219-v1:0": {
        "input_per_1k": 0.003,
        "output_per_1k": 0.015,
    },
    "anthropic.claude-opus-4-20250514-v1:0": {
        "input_per_1k": 0.015,
        "output_per_1k": 0.075,
    },
    "deepseek.r1-v1:0": {
        "input_per_1k": 0.00135,
        "output_per_1k": 0.0054,
    },
    "meta.llama3-70b-instruct-v1:0": {
        "input_per_1k": 0.00265,
        "output_per_1k": 0.0035,
    },
    "meta.llama3-8b-instruct-v1:0": {
        "input_per_1k": 0.0003,
        "output_per_1k": 0.0006,
    },
}


def get_pricing(model_name, input_tokens, output_tokens):
    pricing = MODEL_PRICING.get(model_name)
    if pricing:
        input_cost = (input_tokens / 1000) * pricing["input_per_1k"]
        output_cost = (output_tokens / 1000) * pricing["output_per_1k"]
        total_cost = input_cost + output_cost
        return {
            "input_cost": input_cost,
            "output_cost": output_cost,
            "total_cost": total_cost
        }
    else:
        return None


class TokenTrackingCallback(BaseCallbackHandler):
    def on_llm_end(self, response, **kwargs):
        try:
            generation = response.generations[0][0]  # First generation
            usage = generation.message.usage_metadata
            model = generation.message.response_metadata.get("model_name", "unknown")

            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            total_tokens = usage.get("total_tokens", input_tokens + output_tokens)

            pricing = MODEL_PRICING.get(model)
            if pricing:
                input_cost = (input_tokens / 1000) * pricing["input_per_1k"]
                output_cost = (output_tokens / 1000) * pricing["output_per_1k"]
                total_cost = input_cost + output_cost

                # print(f"[{datetime.now()}] Model: {model}")
                # print(f"  Input tokens: {input_tokens}")
                # print(f"  Output tokens: {output_tokens}")
                # print(f"  Total tokens: {total_tokens}")
                # print(f"  Total cost: ${total_cost:.6f}")
            else:
                print(f"[{datetime.now()}] Model: {model} – Pricing not found")

        except Exception as e:
            print(f"Error in TokenCostTracker.on_llm_end: {e}")
