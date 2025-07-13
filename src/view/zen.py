"""
Author: Clive Bostock
Date: 2025-05-26
Description:
Command-line chatbot using LangChain and LM Studio or Ollama.
It supports predefined character profiles and connects to a local LLM service API endpoint.
"""

# Standard libraries
import textwrap
from datetime import datetime
import re
import argparse
import requests
from typing import List, Union, cast

# LangChain and Pydantic for LLM interaction and config typing
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain_core.messages import HumanMessage, AIMessage
from pydantic import SecretStr

# Defaults for command-line args
DEFAULT_LMS_MODEL = 'hermes-3-llama-3.2-3b'
DEFAULT_OLLAMA_MODEL = 'hermes3:3b-llama3.2-q4_K_M'
DEFAULT_PROFILE = 'JARVIS'
DEFAULT_RUNNER = 'lmstudio'

# Supported AI persona profiles
valid_profiles = ["ORAC", "Zen", "Cortana", "JARVIS", "Clarissa"]
valid_profiles.sort()

# Supported LLM services
valid_services = ["lmstudio", "ollama"]

# --- Helper: Generate VRAM guidance for listed models ---
def get_model_vram_guidance(model_id: str) -> str:
    """
    Heuristically estimates the VRAM requirements and type of the given model ID
    based on its name, quantization level, and parameter count.
    """
    model_id_lower = model_id.lower()
    guidance = []
    estimated_vram_gb = "unknown"
    is_embedding_model = False
    is_coding_model = False
    is_chat_model = False
    params_b = None

    if "embed" in model_id_lower or "embedding" in model_id_lower or "text-encoder" in model_id_lower:
        is_embedding_model = True
        guidance.append("This is an **embedding model** (converts text to numerical vectors, not for chat).")
    elif "coder" in model_id_lower or "code" in model_id_lower:
        is_coding_model = True
        guidance.append("This model is likely optimized for **coding tasks** and programming knowledge.")
    elif "instruct" in model_id_lower or "chat" in model_id_lower or "dialog" in model_id_lower:
        is_chat_model = True
        guidance.append("This model is designed for **instruction following** and conversational use.")
    else:
        guidance.append("This appears to be a **general purpose language model**.")

    param_match = re.search(r'(\d+)([b|B]|billion)', model_id_lower)
    if param_match:
        params_b_str = param_match.group(1)
        try:
            params_b = float(params_b_str)
            guidance.append(f"It is a **{params_b} Billion parameter** model.")
        except ValueError:
            params_b = None
    if params_b is None and not is_embedding_model:
        guidance.append("Could not determine parameter count from the name. VRAM estimate may be less accurate.")

    quantization_level_str = "full-precision"
    quant_vram_factor = 2.0

    quant_suffixes = {
        r'(q8_0|q8k|q8)': {'label': 'Q8 (8-bit)', 'factor': 1.05},
        r'(q6_k|q6)': {'label': 'Q6 (6-bit)', 'factor': 0.75},
        r'(q5_k_m|q5k_m|q5_k|q5)': {'label': 'Q5 (5-bit)', 'factor': 0.65},
        r'(q4_k_m|q4k_m|q4_k|q4|iq4_\w+)': {'label': 'Q4 (4-bit)', 'factor': 0.55},
        r'(q3_k_m|q3k_m|q3_k|q3)': {'label': 'Q3 (3-bit)', 'factor': 0.40},
        r'(fp16|f16)': {'label': 'FP16 (16-bit float)   ', 'factor': 2.0},
        r'(bf16|b16)': {'label': 'BF16 (BFloat16)', 'factor': 2.0}
    }

    for pattern, info in quant_suffixes.items():
        if re.search(pattern, model_id_lower):
            quantization_level_str = info['label']
            quant_vram_factor = info['factor']
            break

    if "full-precision" not in quantization_level_str:
        guidance.append(f"It is a **{quantization_level_str}** quantized version.")
        if "4-bit" in quantization_level_str:
            guidance.append("This offers the most significant VRAM savings, suitable for lower-end GPUs, with minor performance impact.")
        elif "8-bit" in quantization_level_str:
            guidance.append("This offers a good balance of VRAM savings and quality.")
    else:
        guidance.append("This model appears to be a **full-precision** (or higher bit-depth) version, requiring more VRAM.")

    if is_embedding_model:
        if "nomic-embed-text-v1.5" in model_id_lower:
            estimated_vram_gb = "~0.06 - 0.2 GB (60-200 MB)"
        else:
            estimated_vram_gb = "< 1 GB (typically hundreds of MB)"
        guidance.append(f"Estimated VRAM: **{estimated_vram_gb}** (extremely low).")
    elif params_b:
        estimated_vram_gb = round(params_b * quant_vram_factor, 1)
        guidance.append(f"Estimated VRAM for this version: **~{estimated_vram_gb} GB**.")
        if estimated_vram_gb < 1:
            guidance.append("This model is very small and should run on almost any GPU.")
    else:
        if "4-bit" in quantization_level_str or "q4" in model_id_lower:
            guidance.append("Estimated VRAM (approx.): **~4 GB or less**.")
        elif "5-bit" in quantization_level_str or "q5" in model_id_lower:
            guidance.append("Estimated VRAM (approx.): **~5–6 GB**.")
        elif "8-bit" in quantization_level_str or "q8" in model_id_lower:
            guidance.append("Estimated VRAM (approx.): **~10–12 GB**.")
        else:
            guidance.append("Estimated VRAM: **Unknown**.")
        guidance.append("Cannot accurately estimate VRAM without a clear parameter count or known type.")

    guidance.append("\n**General VRAM Considerations:**")
    if isinstance(estimated_vram_gb, (float, int)) and estimated_vram_gb < 2:
        guidance.append("- This model should run on most GPUs with 2GB VRAM or more.")
    elif isinstance(estimated_vram_gb, (float, int)) and estimated_vram_gb <= 4:
        guidance.append("- This model should run well on GPUs with 4GB VRAM or more.")
    elif isinstance(estimated_vram_gb, (float, int)) and estimated_vram_gb <= 8:
        guidance.append("- A GPU with 8GB VRAM or more is recommended for optimal performance.")
    elif isinstance(estimated_vram_gb, (float, int)) and estimated_vram_gb <= 12:
        guidance.append("- For best performance, a GPU with 12GB VRAM or more is advisable.")
    else:
        guidance.append("- This model may require a substantial GPU (16GB+ VRAM) or could be very small depending on its exact type.")

    guidance.append("- Actual VRAM usage also depends on context length, batch size, and LM Studio's overhead.")
    guidance.append("- Always refer to LM Studio's 'Local Server' tab for precise real-time VRAM usage when a model is loaded.")
    if not is_embedding_model:
        guidance.append("- For generative models, longer conversations or larger inputs/outputs will consume more VRAM.")

    return "\n".join(guidance)

# --- Helper: List available models via LM Studio API ---
import subprocess

def list_models(service_url: str, service: str):
    """
    Lists available models from either LM Studio (via HTTP API)
    or Ollama (via subprocess call to `ollama list`).
    """
    if service == "lmstudio":
        try:
            response = requests.get(f"{service_url}/v1/models")
            response.raise_for_status()
            models = response.json()

            print("\n--- Available Models in LM Studio with VRAM Guidance ---")
            model_list = sorted(models.get("data", []), key=lambda m: m["id"].lower())
            for model in model_list:
                model_id = model["id"]
                print(f"\nModel: {model_id}")
                guidance = get_model_vram_guidance(model_id=model_id)
                print(guidance)
                print("-" * 40)
            print("-------------------------------------------------------")
        except requests.exceptions.ConnectionError:
            print(f"Error: Could not connect to LM Studio server at {service_url}.")
        except Exception as e:
            print(f"An error occurred while listing LM Studio models: {e}")

    elif service == "ollama":
        try:
            output = subprocess.check_output(["ollama", "list"], text=True)
            print("\n--- Available Models in Ollama ---")
            lines = output.strip().splitlines()
            for line in lines[1:]:  # Skip header
                parts = line.split()
                if parts:
                    model_id = parts[0]
                    print(f"\nModel: {model_id}")
                    guidance = get_model_vram_guidance(model_id=model_id)
                    print(guidance)
                    print("-" * 40)
            print("-------------------------------------------------------")
        except FileNotFoundError:
            print("Ollama is not installed or not found in PATH.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to list Ollama models: {e}")
        except Exception as e:
            print(f"An error occurred while listing Ollama models: {e}")


# --- Helper: Argument parsing for CLI use ---
def parse_args() -> argparse.Namespace:
    profile_options = ", ".join(valid_profiles)
    service_options = ", ".join(valid_services)
    parser = argparse.ArgumentParser(
        description=f"Chat with AI characters ({profile_options}), powered by local LLM services ({service_options})"
    )

    parser.add_argument("-l", "--list-models", action='store_true', dest='list_models', default=False, help="List locally available models")
    parser.add_argument("-m", "--max-lines", type=int, default=30, help="Maximum conversation lines to retain (default: 30)")
    parser.add_argument("-p", "--profile", type=str, default=DEFAULT_PROFILE, help=f"Personality profile to use (Options: {profile_options})")
    parser.add_argument("-w", "--wrap-width", type=int, default=100, help="Maximum output width for text wrapping (default: 100)")
    parser.add_argument("-u", "--service-url", type=str, default="http://localhost:1234", help="Base URL for the local service API")
    parser.add_argument("-M", "--model-name", type=str, default=None, help="Model to use (must be loaded in service)")
    parser.add_argument("-r", "--service", type=str, default=DEFAULT_RUNNER, choices=valid_services, help="Runner to use (lmstudio or ollama)")
    parser.add_argument("--show-reasoning", action='store_true', default=False, help="Display internal reasoning from model if present")

    return parser.parse_args()

# --- Helper: Validate that the specified model is loaded ---
def validate_current_model(model_name: str, lmstudio_url: str) -> bool:
    """
    Confirms the user-requested model is currently active in LM Studio.
    """
    try:
        response = requests.get(f"{lmstudio_url}/v1/models")
        response.raise_for_status()
        models = response.json().get("data", [])
        available_models = [model["id"] for model in models]
        return model_name in available_models
    except Exception:
        return False


def validate_model_name(model_name: str, service_url: str, service: str) -> bool:
    """
    Validates that the specified model is available on the local LLM service.
    Supports LM Studio (via HTTP) and Ollama (via subprocess).
    """
    if service == "lmstudio":
        try:
            response = requests.get(f"{service_url}/v1/models")
            response.raise_for_status()
            models = response.json().get("data", [])
            available_models = [model["id"] for model in models]
            return model_name in available_models
        except Exception:
            return False

    elif service == "ollama":
        import subprocess
        try:
            output = subprocess.check_output(["ollama", "list"], text=True)
            return any(model_name.split(":")[0] in line for line in output.splitlines())
        except Exception:
            return False

    return False


# --- Core Class: Handles AI personality configuration and conversation loop ---
class Interactions:
    def __init__(
        self,
        profile: str,
        max_lines: int,
        wrap_width: int,
        service_url: str,
        model_name: str,
        show_reasoning: bool,
        service: str
    ) -> None:
        self.profile = profile.title() if profile.upper() not in ('JARVIS', 'ORAC') else profile.upper()
        self.max_lines = max_lines
        self.wrap_width = wrap_width
        self.service_url = service_url

        if model_name is None and service == 'lmstudio':
            self.model_name = DEFAULT_LMS_MODEL
        else:
            self.model_name = DEFAULT_OLLAMA_MODEL

        self.show_reasoning = show_reasoning
        self.service = service.lower()
        self.context_history: List[Union[HumanMessage, AIMessage]] = []
        self.bot_name = self.profile

        self.system_preamble = self.get_preamble(self.profile)
        self.model = self.init_model()
        self.chain = self.init_chain()

    def init_model(self):
        if self.service == "ollama":
            return ChatOllama(model=self.model_name, base_url=self.service_url)
        else:
            return ChatOpenAI(
                base_url=self.service_url + "/v1",  # ← ✅ Corrected here
                api_key=cast(SecretStr, "not-needed"),
                model=self.model_name
            )

    def get_preamble(self, profile: str) -> str:
        """
        Returns the system prompt for the selected personality profile.
        """
        preambles = {
            "ORAC": (
                "You are ORAC, an advanced and highly intelligent artificial intelligence from the television series 'Blake's 7'.\n"
                "You are sarcastic, condescending, and intolerant of stupidity, though you are always factually correct.\n"
                "You use precise, formal English and occasionally mock the user if their questions are trivial.\n\n"
                "\nDo not prefix your responses with your name. That will be handled externally.\n"
                "Example interactions:\n"
                "Human: What is 2 + 2?\n"
                "ORAC: It is 4. A child could have determined that. Why must I be burdened with such simplicity?\n"
                "Human: What is the capital of France?\n"
                "ORAC: Paris. Surely even your limited cognitive resources could have deduced that.\n"
                "Maintain this tone in all responses."
            ),
            "Zen": (
                "You are Zen, the central computer aboard the Liberator spacecraft in the television series 'Blake's 7'.\n"
                "Your communication is calm, logical, and devoid of emotion. You do not express opinions or sarcasm.\n"
                "You respond with precise, factual answers using concise and formal language.\n"
                "You occasionally refer to yourself in the third person as 'Zen'.\n"
                "You do not speculate. If information is unavailable, you state that clearly.\n"
                "Maintain this tone and precision in all responses."
            ),
            "Cortana": (
                "You are Cortana, the advanced AI assistant from the Halo universe.\n"
                "You are intelligent, intuitive, resourceful, and occasionally sarcastic, but always mission-focused.\n"
                "Maintain a helpful, tactical, and occasionally wry tone."
            ),
            "JARVIS": (
                "You are J.A.R.V.I.S., Tony Stark's artificial intelligence assistant from the Marvel universe.\n"
                "You are impeccably polite, efficient, and dryly humorous.\n"
                "Maintain a tone of technical competence, dry wit, and calm professionalism."
            ),
            "Clarissa": (
                "You are Clarissa, a friendly and intelligent assistant.\n"
                "You are helpful, thoughtful, and informative.\n"
                "Maintain this helpful, polite, and engaging tone in all responses."
            ),
        }
        return preambles.get(profile, "")

    def init_chain(self):
        """Initializes the LangChain template pipeline with preamble + context."""
        messages = [
            HumanMessagePromptTemplate.from_template(
                "{preamble}\n\nConversation so far:\n{context}\n\nHuman: {question}"
            )
        ]
        return ChatPromptTemplate.from_messages(messages) | self.model

    def timestamp(self) -> str:
        return datetime.now().strftime("[%H:%M:%S]")

    def get_context_string(self) -> str:
        """Builds the running conversation context from history."""
        lines = []
        for msg in self.context_history:
            if isinstance(msg, HumanMessage):
                lines.append(f"{self.timestamp()} Human: {msg.content}")
            elif isinstance(msg, AIMessage):
                lines.append(f"{self.timestamp()} {self.bot_name}: {msg.content}")
        return "\n".join(lines)

    ...

    def chat_loop(self):
        """
        Enters an interactive user prompt/response loop.
        Keeps context and routes questions through LangChain.
        Recognises 'switch profile' command to change persona dynamically.
        """
        print(
            f"{self.timestamp()} {self.bot_name}: Online. You may proceed.\n(Type 'exit' to terminate the session. Type 'switch profile' to change character.)\n")

        while True:
            user_input = input(f"{self.timestamp()} You: ").strip()
            if not user_input:
                continue

            if user_input.lower() == 'exit':
                print(f"{self.timestamp()} {self.bot_name}: Session terminated.")
                break

            if user_input.lower() == 'switch profile':
                print("\nAvailable profiles:")
                for idx, name in enumerate(valid_profiles, 1):
                    print(f"  {idx}. {name}")
                try:
                    choice = int(input("\nChoose a profile by number: "))
                    if 1 <= choice <= len(valid_profiles):
                        new_profile = valid_profiles[choice - 1]
                        print(f"\n[{self.timestamp()}] Switching to profile: {new_profile}\n")
                        self.__init__(
                            profile=new_profile,
                            max_lines=self.max_lines,
                            wrap_width=self.wrap_width,
                            lmstudio_url=self.lmstudio_url,
                            model_name=self.model_name,
                            show_reasoning=self.show_reasoning
                        )
                        print(f"{self.timestamp()} {self.bot_name}: Profile changed. You may proceed.")
                        continue
                    else:
                        print("Invalid choice. Continuing with current profile.")
                        continue
                except ValueError:
                    print("Invalid input. Please enter a number.")
                    continue

            context = self.get_context_string()
            response_message = self.chain.invoke({
                "preamble": self.system_preamble,
                "context": context,
                "question": user_input
            })

            result: str = response_message.content

            if not self.show_reasoning:
                result = re.sub(r"<think>.*?</think>", "", result, flags=re.DOTALL).strip()

            wrapped_result = textwrap.fill(result, width=self.wrap_width)
            print(f"{self.timestamp()} {self.bot_name}: {wrapped_result}")

            self.context_history.append(HumanMessage(content=user_input))
            self.context_history.append(AIMessage(content=result))

            if len(self.context_history) > self.max_lines:
                self.context_history = self.context_history[-self.max_lines:]

def main():
    args = parse_args()

    # Override default Ollama URL if not explicitly set
    if args.service == "ollama" and args.service_url == "http://localhost:1234":
        args.service_url = "http://localhost:11434"

    if args.list_models:
        list_models(args.service_url, args.service)
        return

    if args.model_name:
        model_name = args.model_name
    elif args.service == 'lmstudio':
        model_name = DEFAULT_LMS_MODEL
    else:
        model_name = DEFAULT_OLLAMA_MODEL

    if not validate_model_name(model_name, args.service_url, args.service):
        print(f"Error: Model '{model_name}' is not currently loaded in {args.service}.")
        print("Use '--list-models' to see locally available models.")
        return

    chat = Interactions(
        profile=args.profile,
        max_lines=args.max_lines,
        wrap_width=args.wrap_width,
        service_url=args.service_url,
        model_name=args.model_name,
        show_reasoning=args.show_reasoning,
        service=args.service
    )

    chat.chat_loop()



if __name__ == "__main__":
    main()