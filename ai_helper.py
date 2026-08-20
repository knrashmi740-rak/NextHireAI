from groq import Groq
from dotenv import load_dotenv
import os


load_dotenv()

generated_questions = {}
client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)



def generate_questions(company):
    previous_questions = ""

    for company_name, questions in generated_questions.items():

       previous_questions += f"""

    Questions already used for {company_name}:

    {questions}

     """


    company_details = {

        "Google": """
Focus on Google's interview style:
- Strong Data Structures and Algorithms
- Problem solving
- System design
- Googleyness and behavioral questions
- Large scale systems
""",


        "Microsoft": """
Focus on Microsoft's interview style:
- DSA
- Object Oriented Programming
- Operating Systems
- Cloud and Azure concepts
- Team collaboration questions
""",


        "Amazon": """
Focus on Amazon's interview style:
- Leadership Principles
- DSA coding rounds
- Object oriented design
- Real-world problem solving
- Behavioral questions
""",


        "TCS": """
Focus on TCS placement pattern:
- Aptitude
- Programming basics
- C, C++, Java, Python
- DBMS
- HR questions
""",


        "Infosys": """
Focus on Infosys interview pattern:
- Logical reasoning
- Programming fundamentals
- SQL
- Java/Python basics
- HR round
""",


        "Wipro": """
Focus on Wipro hiring pattern:
- Coding basics
- Technical fundamentals
- Communication skills
- HR questions
"""

    }


    style = company_details.get(
        company,
        "Focus on this company's placement interview pattern."
    )



    prompt = f"""

You are NextHireAI, an expert placement preparation assistant.

Create a UNIQUE interview preparation guide for {company}.

Company interview style:

{style}

Avoid using these questions because they are already used:

{previous_questions}
Generate:

1. Coding Round
- 5 commonly asked coding problems
- Mention concepts tested


2. Technical Round
- 5 technical questions based on company expectations


3. HR Round
- 5 HR questions specific to this company


4. Preparation Strategy
- How students should prepare for {company}


Rules:
- Do not repeat questions from other companies.
- Do not use generic repeated questions.
- Make questions specific to {company}.
- Do not use tables.
- Do not use #, *, or | symbols.
- Use numbered lists.
- Keep the format compact.
"""


    response = client.chat.completions.create(

        model="openai/gpt-oss-120b",

        messages=[
            {
                "role":"user",
                "content":prompt
            }
        ],

        temperature=0.9

    )

    result = response.choices[0].message.content


    generated_questions[company] = result


    return result

def generate_mcq(section, topics):

    topic_text = ", ".join(topics)

    prompt = f"""
You are NextHireAI, an expert placement preparation assistant.

Generate exactly ONE multiple-choice question for:

Section:
{section}

Allowed topics:
{topic_text}

STRICT RULES:

1. The question MUST belong to the given section.
2. The question MUST come from ONLY one of the allowed topics.
3. Do not ask anything outside these topics.
4. Generate exactly four options.
5. Only one option must be correct.
6. Give a short and clear explanation.
7. The question should be suitable for engineering placement exams.
8. Return ONLY valid JSON.
9. Do not use markdown.
10. Do not put ``` around the JSON.

Return exactly this format:

{{
    "topic": "topic name",
    "question": "question text",
    "options": [
        "option A",
        "option B",
        "option C",
        "option D"
    ],
    "answer": "option A",
    "explanation": "short explanation"
}}
"""

    response = client.chat.completions.create(

        model="openai/gpt-oss-120b",

        messages=[
            {
                "role": "system",
                "content": "You generate accurate placement MCQs."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],

        temperature=0.7,

        max_tokens=600
    )

    result = response.choices[0].message.content.strip()

    # Remove code fences if the AI accidentally adds them

    if result.startswith("```"):

        result = result.replace("```json", "")
        result = result.replace("```", "")
        result = result.strip()

    import json

    return json.loads(result)