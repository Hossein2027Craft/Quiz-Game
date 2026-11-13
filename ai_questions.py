
import json
import os
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("کلید OPENAI_API_KEY پیدا نشد!")
client = OpenAI(api_key=api_key)
def generate_question(difficulty="hard"):
    prompt = f"""
    برای بازی مسابقه اطلاعات عمومی یک سؤال فارسی طراحی کن.
    سطح دشواری: {difficulty}
    شرایط:
    - چهار گزینه داشته باشد.
    - فقط یک گزینه صحیح باشد.
    - سؤال تکراری یا مبهم نباشد.
    - پاسخ صحیح را با حرف A یا B یا C یا D مشخص کن.
    خروجی فقط JSON معتبر باشد و دقیقاً این ساختار را داشته باشد:
    {{
        "question": "متن سؤال",
        "options": {{
            "A": "گزینه اول",
            "B": "گزینه دوم",
            "C": "گزینه سوم",
            "D": "گزینه چهارم"
        }},
        "correct_answer": "B",
        "explanation": "توضیح کوتاه پاسخ صحیح"
    }}
    """
    response = client.responses.create(
        model="gpt-6-luna",
        input=prompt
    )
    raw_text = response.output_text.strip()
    # حذف علامت های احتمالی Markdown
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[1]
        raw_text = raw_text.rsplit("```", 1)[0].strip()
    # تبدیل متن JSON به اطلاعات پایتون
    data = json.loads(raw_text)
    # بررسی ساختار سؤال
    if not all(key in data for key in (
        "question",
        "options",
        "correct_answer",
        "explanation"
    )):
        raise ValueError("ساختار سؤال معتبر نیست.")
    if set(data["options"]) != {"A", "B", "C", "D"}:
        raise ValueError("سؤال باید دقیقاً چهار گزینه داشته باشد.")
    if data["correct_answer"] not in {"A", "B", "C", "D"}:
        raise ValueError("پاسخ صحیح معتبر نیست.")
    return data
if __name__ == "__main__":
    question = generate_question()
    print(json.dumps(
        question,
        ensure_ascii=False,
        indent=2
    ))