import json
import time
from pathlib import Path
from datetime import datetime

import streamlit as st
from google import genai
from google.genai import types


CONFIG_FILE = Path("config.json")
USAGE_FILE = Path("gemini_usage_history.json")

MAX_RETRIES = 5
INITIAL_RETRY_DELAY = 2
USD_TO_INR = 95.13

PRICING = {
    "gemini-3.8-flash": {
        "input": 0.75,
        "output": 3.75
    },
    "gemini-3.7-flash": {
        "input": 0.75,
        "output": 3.75
    },
    "gemini-3.6-flash": {
        "input": 0.75,
        "output": 3.75
    },
    "gemini-3.5-flash-lite": {
        "input": 0.30,
        "output": 2.50
    }
}


st.set_page_config(
    page_title="Gemini Usage Monitor",
    layout="wide"
)


# def load_config():

#     if not CONFIG_FILE.exists():
#         st.error(
#             "config.json was not found."
#         )
#         st.stop()

#     try:

#         with open(
#             CONFIG_FILE,
#             "r",
#             encoding="utf-8"
#         ) as file:

#             config = json.load(file)

#     except json.JSONDecodeError as error:

#         st.error(
#             f"config.json contains invalid JSON: {error}"
#         )
#         st.stop()

#     api_key = config.get(
#         "gemini_api_key"
#     )

#     model = config.get(
#         "model"
#     )

#     if not api_key:

#         st.error(
#             "gemini_api_key is missing from config.json."
#         )
#         st.stop()

#     if not model:

#         st.error(
#             "model is missing from config.json."
#         )
#         st.stop()

#     return api_key, model

def load_config():
    if "gemini_api_key" in st.secrets:
        return {
            "gemini_api_key": st.secrets["gemini_api_key"],
            "model": st.secrets.get("model", "gemini-3.5-flash-lite")
        }

    with open(CONFIG_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def load_history():

    if not USAGE_FILE.exists():
        return []

    try:

        with open(
            USAGE_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        if isinstance(data, list):
            return data

    except Exception:
        pass

    return []


def save_history(history):

    with open(
        USAGE_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            history,
            file,
            indent=2,
            ensure_ascii=False
        )


def get_number(value):

    if value is None:
        return 0

    try:

        return int(value)

    except Exception:

        return 0


def get_usage(metadata, field):

    if metadata is None:
        return 0

    return get_number(
        getattr(
            metadata,
            field,
            None
        )
    )


def get_pricing(model):

    if model in PRICING:
        return PRICING[model]

    for known_model in PRICING:

        if model.startswith(
            known_model
        ):

            return PRICING[
                known_model
            ]

    return None


def calculate_cost(
    model,
    input_tokens,
    output_tokens,
    thinking_tokens
):

    pricing = get_pricing(
        model
    )

    if pricing is None:
        return None

    input_cost = (
        input_tokens / 1_000_000
    ) * pricing["input"]

    output_cost = (
        (output_tokens + thinking_tokens)
        / 1_000_000
    ) * pricing["output"]

    return {
        "input_cost": input_cost,
        "output_cost": output_cost,
        "total_cost": (
            input_cost +
            output_cost
        )
    }


def inr(value):

    if value is None:
        return "N/A"

    return f"₹{value * USD_TO_INR:,.8f}"


def create_client(api_key):

    return genai.Client(
        api_key=api_key
    )


def create_chat(
    client,
    model
):

    return client.chats.create(
        model=model,
        config=types.GenerateContentConfig(
            system_instruction=(
                "Talk to the user like their best friend. "
                "Be warm, natural, casual, helpful, and direct. "
                "Always respond in exactly one line. "
                "Do not use line breaks. "
                "Do not use unnecessary formatting. "
                "Give the complete and useful answer naturally."
            )
        )
    )


def send_message_with_retry(
    chat,
    prompt
):

    last_error = None

    for attempt in range(
        MAX_RETRIES
    ):

        try:

            response = chat.send_message(
                prompt
            )

            return response

        except Exception as error:

            last_error = error

            error_text = str(
                error
            ).upper()

            retryable = (
                "503" in error_text
                or
                "UNAVAILABLE" in error_text
                or
                "429" in error_text
                or
                "RESOURCE_EXHAUSTED" in error_text
                or
                "500" in error_text
                or
                "INTERNAL" in error_text
                or
                "TIMEOUT" in error_text
                or
                "DEADLINE" in error_text
            )

            if not retryable:
                raise

            if attempt >= (
                MAX_RETRIES - 1
            ):
                raise

            delay = (
                INITIAL_RETRY_DELAY
                * (2 ** attempt)
            )

            time.sleep(
                delay
            )

    raise last_error


# api_key, model = load_config()

api_key = "AQ.Ab8RN6KaU4ux4n_HJjcsj-eH1xz1TsHArj4UcDY7DL_a0S5AjA"

model = "gemini-3.5-flash-lite"


if "history" not in st.session_state:

    st.session_state.history = (
        load_history()
    )


if "messages" not in st.session_state:

    st.session_state.messages = []


if "client" not in st.session_state:

    st.session_state.client = (
        create_client(
            api_key
        )
    )


if "chat" not in st.session_state:

    st.session_state.chat = (
        create_chat(
            st.session_state.client,
            model
        )
    )


if "chat_model" not in st.session_state:

    st.session_state.chat_model = model


if (
    st.session_state.chat_model
    != model
):

    st.session_state.chat = (
        create_chat(
            st.session_state.client,
            model
        )
    )

    st.session_state.chat_model = model


st.title(
    "Gemini API Usage Monitor"
)

st.caption(
    f"Model: {model}"
)


left, right = st.columns(
    [1.25, 1],
    gap="large"
)


with left:

    st.subheader(
        "Chat"
    )


    for message in (
        st.session_state.messages
    ):

        with st.chat_message(
            message["role"]
        ):

            st.markdown(
                message["content"]
            )

            usage = message.get(
                "usage"
            )

            if usage:

                input_tokens = get_number(
                    usage.get(
                        "input_tokens"
                    )
                )

                output_tokens = get_number(
                    usage.get(
                        "output_tokens"
                    )
                )

                total_tokens = get_number(
                    usage.get(
                        "total_tokens"
                    )
                )

                st.caption(
                    f"Input: "
                    f"{input_tokens:,} | "
                    f"Output: "
                    f"{output_tokens:,} | "
                    f"Total: "
                    f"{total_tokens:,}"
                )


    prompt = st.chat_input(
        "Send a message to Gemini"
    )


    if prompt:

        st.session_state.messages.append(
            {
                "role": "user",
                "content": prompt
            }
        )


        with st.chat_message(
            "user"
        ):

            st.markdown(
                prompt
            )


        with st.chat_message(
            "assistant"
        ):

            try:

                with st.spinner(
                    "Waiting for Gemini..."
                ):

                    response = (
                        send_message_with_retry(
                            st.session_state.chat,
                            prompt
                        )
                    )


                answer = (
                    response.text
                    or ""
                )


                answer = (
                    answer
                    .replace(
                        "\r",
                        " "
                    )
                    .replace(
                        "\n",
                        " "
                    )
                    .strip()
                )


                st.markdown(
                    answer
                )


                metadata = (
                    response.usage_metadata
                )


                input_tokens = (
                    get_usage(
                        metadata,
                        "prompt_token_count"
                    )
                )


                output_tokens = (
                    get_usage(
                        metadata,
                        "candidates_token_count"
                    )
                )


                total_tokens = (
                    get_usage(
                        metadata,
                        "total_token_count"
                    )
                )


                thinking_tokens = (
                    get_usage(
                        metadata,
                        "thoughts_token_count"
                    )
                )


                cached_tokens = (
                    get_usage(
                        metadata,
                        "cached_content_token_count"
                    )
                )


                cost = calculate_cost(
                    model,
                    input_tokens,
                    output_tokens,
                    thinking_tokens
                )


                if cost:

                    input_cost = (
                        cost["input_cost"]
                    )

                    output_cost = (
                        cost["output_cost"]
                    )

                    total_cost = (
                        cost["total_cost"]
                    )

                else:

                    input_cost = None
                    output_cost = None
                    total_cost = None


                request_number = (
                    len(
                        st.session_state.history
                    ) + 1
                )


                record = {

                    "request_number":
                        request_number,

                    "timestamp":
                        datetime.now().isoformat(
                            timespec="seconds"
                        ),

                    "model":
                        model,

                    "request":
                        prompt,

                    "response":
                        answer,

                    "input_tokens":
                        input_tokens,

                    "output_tokens":
                        output_tokens,

                    "thinking_tokens":
                        thinking_tokens,

                    "cached_tokens":
                        cached_tokens,

                    "total_tokens":
                        total_tokens,

                    "paid_input_cost_usd":
                        input_cost,

                    "paid_output_cost_usd":
                        output_cost,

                    "paid_total_cost_usd":
                        total_cost,

                    "actual_free_tier_charge_usd":
                        0.0
                }


                st.session_state.history.append(
                    record
                )


                save_history(
                    st.session_state.history
                )


                st.session_state.messages.append(
                    {
                        "role":
                            "assistant",

                        "content":
                            answer,

                        "usage": {

                            "input_tokens":
                                input_tokens,

                            "output_tokens":
                                output_tokens,

                            "thinking_tokens":
                                thinking_tokens,

                            "cached_tokens":
                                cached_tokens,

                            "total_tokens":
                                total_tokens
                        }
                    }
                )


                st.caption(
                    f"Input: "
                    f"{input_tokens:,} | "
                    f"Output: "
                    f"{output_tokens:,} | "
                    f"Total: "
                    f"{total_tokens:,}"
                )


                st.rerun()


            except Exception as error:

                st.error(
                    f"Gemini API request failed:\n\n"
                    f"{error}"
                )


with right:

    st.subheader(
        "Usage"
    )


    history = (
        st.session_state.history
    )


    total_requests = len(
        history
    )


    total_responses = len(
        history
    )


    total_input_tokens = sum(
        get_number(
            item.get(
                "input_tokens"
            )
        )
        for item in history
    )


    total_output_tokens = sum(
        get_number(
            item.get(
                "output_tokens"
            )
        )
        for item in history
    )


    total_thinking_tokens = sum(
        get_number(
            item.get(
                "thinking_tokens"
            )
        )
        for item in history
    )


    total_cached_tokens = sum(
        get_number(
            item.get(
                "cached_tokens"
            )
        )
        for item in history
    )


    total_tokens = sum(
        get_number(
            item.get(
                "total_tokens"
            )
        )
        for item in history
    )

    total_paid_cost = sum(
        float(
            item.get(
                "paid_total_cost_usd"
            ) or 0
        )
        for item in history
    )


    col1, col2 = st.columns(
        2
    )


    with col1:

        st.metric(
            "Requests",
            f"{total_requests:,}"
        )


    with col2:

        st.metric(
            "Responses",
            f"{total_responses:,}"
        )


    col1, col2 = st.columns(
        2
    )


    with col1:

        st.metric(
            "Input Tokens",
            f"{total_input_tokens:,}"
        )


    with col2:

        st.metric(
            "Output Tokens",
            f"{total_output_tokens:,}"
        )


    col1, col2 = st.columns(
        2
    )


    with col1:

        st.metric(
            "Total Tokens",
            f"{total_tokens:,}"
        )


    with col2:

        st.metric(
            "Thinking Tokens",
            f"{total_thinking_tokens:,}"
        )


    st.metric(
        "Cached Tokens",
        f"{total_cached_tokens:,}"
    )


    st.divider()


    st.subheader(
        "Cost"
    )


    st.metric(
        "Paid Tier Equivalent",
        inr(
            total_paid_cost
        )
    )


    st.caption(
        "Paid Tier Equivalent is calculated from "
        "the actual Gemini token usage returned "
        "by the API. It is not a Google billing invoice."
    )


    if history:

        st.divider()


        st.subheader(
            "Latest Request"
        )


        latest = history[-1]


        st.write(
            f"Request: "
            f"{latest.get('request_number', 0)}"
        )


        st.write(
            f"Time: "
            f"{latest.get('timestamp', '')}"
        )


        st.write(
            f"Model: "
            f"{latest.get('model', model)}"
        )


        latest_input = get_number(
            latest.get(
                "input_tokens"
            )
        )


        latest_output = get_number(
            latest.get(
                "output_tokens"
            )
        )


        latest_thinking = get_number(
            latest.get(
                "thinking_tokens"
            )
        )


        latest_cached = get_number(
            latest.get(
                "cached_tokens"
            )
        )


        latest_total = get_number(
            latest.get(
                "total_tokens"
            )
        )


        st.write(
            f"Input Tokens: "
            f"{latest_input:,}"
        )


        st.write(
            f"Output Tokens: "
            f"{latest_output:,}"
        )


        st.write(
            f"Thinking Tokens: "
            f"{latest_thinking:,}"
        )


        st.write(
            f"Cached Tokens: "
            f"{latest_cached:,}"
        )


        st.write(
            f"Total Tokens: "
            f"{latest_total:,}"
        )


        st.write(
            f"Input Cost Equivalent: "
            f"{inr(latest.get('paid_input_cost_usd'))}"
        )


        st.write(
            f"Output Cost Equivalent: "
            f"{inr(latest.get('paid_output_cost_usd'))}"
        )


        st.write(
            f"Total Cost Equivalent: "
            f"{inr(latest.get('paid_total_cost_usd'))}"
        )


        st.write(
            "Actual Free Tier Charge: $0.00"
        )


    if history:

        st.divider()


        st.subheader(
            "Request History"
        )


        table = []


        for item in history:

            table.append(
                {
                    "Request":
                        item.get(
                            "request_number",
                            0
                        ),

                    "Time":
                        item.get(
                            "timestamp",
                            ""
                        ),

                    "Model":
                        item.get(
                            "model",
                            ""
                        ),

                    "Input":
                        get_number(
                            item.get(
                                "input_tokens"
                            )
                        ),

                    "Output":
                        get_number(
                            item.get(
                                "output_tokens"
                            )
                        ),

                    "Thinking":
                        get_number(
                            item.get(
                                "thinking_tokens"
                            )
                        ),

                    "Cached":
                        get_number(
                            item.get(
                                "cached_tokens"
                            )
                        ),

                    "Total":
                        get_number(
                            item.get(
                                "total_tokens"
                            )
                        ),

                    "Paid Equivalent":
                        inr(
                            item.get(
                                "paid_total_cost_usd"
                            )
                        ),

                    "Free Tier":
                        "₹0.00"
                }
            )


        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True
        )


    st.divider()


    if st.button(
        "Clear Local Usage History"
    ):

        st.session_state.history = []

        st.session_state.messages = []

        if USAGE_FILE.exists():

            USAGE_FILE.unlink()

        st.rerun()
