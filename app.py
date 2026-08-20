from flask import Flask, render_template, request, redirect, url_for, session,jsonify,flash
from config import Config
from database.models import db, User, AIInterviewQuestion, PracticeProgress
from ai_helper import generate_questions,generate_mcq
import markdown
import os
import json
import time
import uuid
from groq import Groq
from flask_mail import Mail, Message
app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "dev-secret-key"
)
app.config.from_object(Config)

# =========================================================
# EMAIL CONFIGURATION
# =========================================================

app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True

app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")

app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_USERNAME")

mail = Mail(app)

# =========================================================
# DATABASE
# =========================================================

db.init_app(app)

# =========================================================
# GROQ AI CLIENT
# =========================================================

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)
else:
    groq_client = None

# =========================================================
# HR INTERVIEW SESSIONS
# =========================================================

hr_sessions = {}
# =========================================================
# GD SESSIONS
# =========================================================

gd_sessions = {}


ai_interview_sessions = {}

# Create database tables
# =========================================================
# CREATE / UPDATE DATABASE TABLES
# =========================================================

with app.app_context():

    db.create_all()

    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)

    existing_columns = {
        column["name"]
        for column in inspector.get_columns("users")
    }

    # =====================================================
    # NOTIFICATION COLUMNS
    # =====================================================

    if "ai_interview_notifications" not in existing_columns:

        db.session.execute(
            text("""
                ALTER TABLE users
                ADD COLUMN ai_interview_notifications
                BOOLEAN NOT NULL DEFAULT 1
            """)
        )

    if "daily_practice_notifications" not in existing_columns:

        db.session.execute(
            text("""
                ALTER TABLE users
                ADD COLUMN daily_practice_notifications
                BOOLEAN NOT NULL DEFAULT 1
            """)
        )

    if "weekly_progress_notifications" not in existing_columns:

        db.session.execute(
            text("""
                ALTER TABLE users
                ADD COLUMN weekly_progress_notifications
                BOOLEAN NOT NULL DEFAULT 0
            """)
        )


    # =====================================================
    # PROFILE COLUMNS
    # =====================================================

    if "phone" not in existing_columns:

        db.session.execute(
            text("""
                ALTER TABLE users
                ADD COLUMN phone VARCHAR(20)
            """)
        )


    if "location" not in existing_columns:

        db.session.execute(
            text("""
                ALTER TABLE users
                ADD COLUMN location VARCHAR(100)
            """)
        )


    if "graduation_year" not in existing_columns:

        db.session.execute(
            text("""
                ALTER TABLE users
                ADD COLUMN graduation_year VARCHAR(10)
            """)
        )


    if "career_goal" not in existing_columns:

        db.session.execute(
            text("""
                ALTER TABLE users
                ADD COLUMN career_goal VARCHAR(150)
            """)
        )


    if "about" not in existing_columns:

        db.session.execute(
            text("""
                ALTER TABLE users
                ADD COLUMN about TEXT
            """)
        )


    if "skills" not in existing_columns:

        db.session.execute(
            text("""
                ALTER TABLE users
                ADD COLUMN skills TEXT
            """)
        )


    if "profile_picture" not in existing_columns:

        db.session.execute(
            text("""
                ALTER TABLE users
                ADD COLUMN profile_picture VARCHAR(255)
            """)
        )


    # =====================================================
    # SAVE ALL DATABASE CHANGES
    # =====================================================

    db.session.commit()


# ---------------- SPLASH ----------------

@app.route("/")
def splash():
    return render_template("splash.html")


@app.route("/home")
def home():

    alert = request.args.get("alert")

    return render_template(
        "home.html",
        alert=alert
    )

# ---------------- REGISTER ----------------

@app.route("/register", methods=["GET","POST"])
def register():

    if request.method == "POST":

        fullname = request.form["fullname"]
        email = request.form["email"]
        college = request.form["college"]
        branch = request.form["branch"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]


        if password != confirm_password:
            return "Passwords do not match"



        existing_user = User.query.filter_by(email=email).first()


        if existing_user:
            return "Email already registered"



        user = User(

            fullname=fullname,
            email=email,
            college=college,
            branch=branch,
            password=password

        )


        db.session.add(user)

        db.session.commit()


        return redirect(url_for("dashboard"))


    return render_template("register.html")





# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"].strip()
        password = request.form["password"]

        user = User.query.filter_by(
            email=email
        ).first()

        if user and user.password == password:

            # Store the user's ID in the session
            # This is required for Profile, Settings, etc.
            session["user_id"] = user.id

            # You can also keep the user's name
            session["user"] = user.fullname

            return redirect(
                url_for("dashboard")
            )

        else:

            return "Invalid Email or Password"

    return render_template("login.html")
@app.route("/start-practice")
def start_practice():

    if "user" not in session:

        return redirect(
            url_for(
                "home",
                alert="⚠️ Please login first to start your practice journey 🚀"
            )
        )

    return redirect(url_for("practice"))
@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("home"))


@app.route("/dashboard")
def dashboard():

    # -----------------------------------------
    # LOGIN CHECK
    # -----------------------------------------

    if "user" not in session:
        return redirect(
            url_for(
                "home",
                alert="⚠️ Please login first."
            )
        )

    # -----------------------------------------
    # GET CURRENT USER
    # -----------------------------------------

    user = User.query.filter_by(
        fullname=session["user"]
    ).first()

    if not user:
        session.clear()

        return redirect(
            url_for("home")
        )

    # -----------------------------------------
    # PRACTICE TYPES
    # -----------------------------------------

    practice_types = [
        "aptitude",
        "coding",
        "technical",
        "hr",
        "gd",
        "ai_interview"
    ]

    progress = {}

    # -----------------------------------------
    # GET PROGRESS
    # -----------------------------------------

    for practice_type in practice_types:

        record = PracticeProgress.query.filter_by(
            user_id=user.id,
            practice_type=practice_type
        ).first()

        if record:

            progress[practice_type] = {
                "completed": record.completed,
                "total": record.total,
                "percentage": record.percentage
            }

        else:

            progress[practice_type] = {
                "completed": 0,
                "total": 0,
                "percentage": 0
            }

    # -----------------------------------------
    # OVERALL PROGRESS
    # -----------------------------------------

    total_completed = sum(
        item["completed"]
        for item in progress.values()
    )

    total_questions = sum(
        item["total"]
        for item in progress.values()
    )

    if total_questions > 0:

        overall_percentage = round(
            (total_completed / total_questions) * 100
        )

    else:

        overall_percentage = 0

    # -----------------------------------------
    # DASHBOARD
    # -----------------------------------------

    return render_template(
        "dashboard.html",

        user=user,

        progress=progress,

        overall_percentage=overall_percentage
    )





@app.route("/placement-roadmap")
def placement_roadmap():

    return render_template("placement_roadmap.html")
# ---------------- PRACTICE ----------------


@app.route("/practice")
def practice():

    return render_template("practice.html")



@app.route("/aptitude")
def aptitude():

    return render_template("aptitude.html")
@app.route('/quantitative')
def quantitative():
    return render_template('quantitative.html')


@app.route('/logical')
def logical():
    return render_template('logical.html')


@app.route('/verbal')
def verbal():
    return render_template('verbal.html')

@app.route('/quant-learn')
def quant_learn():
    return render_template('quant_learn.html')

@app.route('/learn/percentage')
def percentage():
    return render_template('percentage.html')
@app.route('/learn/number-system')
def number_system():
    return render_template('number_system.html')


@app.route('/learn/profit-loss')
def profit_loss():
    return render_template('profit_loss.html')


@app.route('/learn/time-work')
def time_work():
    return render_template('time_work.html')
@app.route('/learn/probability')
def probability():
    return render_template('probability.html')


@app.route('/learn/ratio-proportion')
def ratio_proportion():
    return render_template('ratio_proportion.html')


@app.route('/learn/average')
def average():
    return render_template('average.html')
@app.route('/learn/simple-interest')
def simple_interest():
    return render_template('simple_interest.html')


@app.route('/learn/compound-interest')
def compound_interest():
    return render_template('compound_interest.html')


@app.route('/learn/time-speed-distance')
def time_speed_distance():
    return render_template('time_speed_distance.html')
@app.route('/learn/permutation-combination')
def permutation_combination():
    return render_template('permutation_combination.html')


@app.route('/learn/data-interpretation')
def data_interpretation():
    return render_template('data_interpretation.html')


@app.route('/learn/simplification')
def simplification():
    return render_template('simplification.html')

@app.route('/learn/algebra')
def algebra():
    return render_template('algebra.html')


@app.route('/learn/mixtures')
def mixtures():
    return render_template('mixtures.html')


@app.route('/learn/pipes_cisterns')
def pipes_cisterns():
    return render_template('pipes_cisterns.html')


@app.route('/learn/partnership')
def partnership():
    return render_template('partnership.html')
@app.route('/learn/hcf_lcm')
def hcf_lcm():
    return render_template('hcf_lcm.html')


@app.route('/learn/ages')
def ages():
    return render_template('ages.html')
@app.route('/learn/sequence_series')
def sequence_series():
    return render_template('sequence_series.html')

@app.route('/learn/blood_relation')
def blood_relation():
    return render_template('blood_relation.html')


@app.route('/learn/direction_sense')
def direction_sense():
    return render_template('direction_sense.html')


@app.route('/learn/seating_arrangement')
def seating_arrangement():
    return render_template('seating_arrangement.html')

@app.route('/learn/syllogism')
def syllogism():
    return render_template('syllogism.html')


@app.route('/learn/venn_diagram')
def venn_diagram():
    return render_template('venn_diagram.html')

@app.route('/learn/statement_conclusion')
def statement_conclusion():
    return render_template('statement_conclusion.html')


@app.route('/learn/data_sufficiency')
def data_sufficiency():
    return render_template('data_sufficiency.html')


@app.route('/learn/analogy')
def analogy():
    return render_template('analogy.html')

@app.route('/learn/classification')
def classification():
    return render_template('classification.html')

@app.route('/verbal-learn')
def verbal_learn():
    return render_template('verbal_learn.html')

@app.route('/learn/parts_of_speech')
def parts_of_speech():
    return render_template('parts_of_speech.html')


@app.route('/learn/tenses')
def tenses():
    return render_template('tenses.html')


@app.route('/learn/articles')
def articles():
    return render_template('articles.html')

@app.route('/learn/prepositions')
def prepositions():
    return render_template('prepositions.html')


@app.route('/learn/subject_verb_agreement')
def subject_verb_agreement():
    return render_template('subject_verb_agreement.html')


@app.route('/learn/active_passive_voice')
def active_passive_voice():
    return render_template('active_passive_voice.html')

@app.route('/learn/direct_indirect_speech')
def direct_indirect_speech():
    return render_template('direct_indirect_speech.html')


@app.route('/learn/synonyms_antonyms')
def synonyms_antonyms():
    return render_template('synonyms_antonyms.html')


@app.route('/learn/one_word_substitution')
def one_word_substitution():
    return render_template('one_word_substitution.html')

@app.route('/learn/idioms_phrases')
def idioms_phrases():
    return render_template('idioms_phrases.html')


@app.route('/learn/sentence_completion')
def sentence_completion():
    return render_template('sentence_completion.html')


@app.route('/learn/error_detection')
def error_detection():
    return render_template('error_detection.html')

@app.route('/learn/spelling_test')
def spelling_test():
    return render_template('spelling_test.html')


@app.route('/learn/reading_comprehension')
def reading_comprehension():
    return render_template('reading_comprehension.html')


@app.route('/learn/sentence_correction')
def sentence_correction():
    return render_template('sentence_correction.html')

@app.route('/learn/para_jumbles')
def para_jumbles():
    return render_template('para_jumbles.html')


@app.route('/learn/cloze_test')
def cloze_test():
    return render_template('cloze_test.html')

@app.route('/logical-learn')
def logical_learn():
    return render_template('logical_learn.html')


@app.route("/coding")
def coding():

    return render_template("coding.html")



# =========================================================
# HR INTERVIEW
# =========================================================

@app.route("/hr")
def hr():
    return render_template("hr.html")


# =========================================================
# HR INTERVIEW - FIRST QUESTION
# =========================================================

@app.route("/hr/interview/<interview_type>/start")
def hr_interview_start(interview_type):

    allowed_types = {
        "basic": "Basic HR Interview",
        "placement": "Placement HR Interview",
        "situational": "Situational Interview"
    }

    if interview_type not in allowed_types:
        return "HR Interview type not found", 404

    if groq_client is None:
        return "GROQ_API_KEY is not configured.", 500

    interview_name = allowed_types[interview_type]

    prompt = f"""
You are conducting a {interview_name}
for an engineering student preparing for placements.

Generate the FIRST HR interview question.

Rules:
- Ask exactly ONE question.
- Make it suitable for a college student.
- Be professional.
- Do not provide the answer.
- Do not number the question.

Return ONLY valid JSON:

{{
    "question": "Your HR interview question"
}}
"""

    try:

        response = groq_client.chat.completions.create(
            model="openai/gpt-oss-120b",

            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a professional HR interviewer. "
                        "Return only valid JSON."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],

            temperature=0.7,
            max_completion_tokens=300,

            response_format={
                "type": "json_object"
            }
        )

        result = response.choices[0].message.content.strip()

        data = json.loads(result)

        question = data.get("question", "").strip()

        if not question:
            return "Unable to generate HR question.", 500

        # Create fresh session
        hr_sessions[interview_type] = {
            "question_number": 1,
            "questions": [question],
            "answers": [],
            "feedback": []
        }

        return render_template(
            "hr_interview.html",
            interview_type=interview_type,
            interview_name=interview_name,
            question=question,
            feedback=None,
            answer=None
        )

    except Exception as e:

        print("\n==============================")
        print("GROQ FIRST HR QUESTION ERROR")
        print(str(e))
        print("==============================\n")

        return "Groq error: " + str(e), 500


# =========================================================
# HR INTERVIEW - ASK / SUBMIT ANSWER
# =========================================================

@app.route("/hr/interview/<interview_type>/ask", methods=["POST"])
def hr_interview_ask(interview_type):

    allowed_types = {
        "basic": "Basic HR Interview",
        "placement": "Placement HR Interview",
        "situational": "Situational Interview"
    }

    if interview_type not in allowed_types:
        return "HR Interview type not found", 404

    if groq_client is None:
        return "GROQ_API_KEY is not configured.", 500

    candidate_answer = request.form.get("answer", "").strip()

    if not candidate_answer:
        return redirect(
            url_for(
                "hr_interview",
                interview_type=interview_type
            )
        )

    # Get current session
    interview_session = hr_sessions.get(
        interview_type
    )

    if not interview_session:
        return redirect(
            url_for(
                "hr_interview_start",
                interview_type=interview_type
            )
        )

    previous_questions = interview_session.get(
        "questions",
        []
    )

    previous_text = ""

    if previous_questions:
        previous_text = "\n".join(
            [
                f"- {q}"
                for q in previous_questions
            ]
        )

    interview_name = allowed_types[interview_type]

    # =====================================================
    # GROQ PROMPT
    # =====================================================

    prompt = f"""
You are an AI HR interviewer conducting a
{interview_name} for an engineering student.

The candidate has just answered:

"{candidate_answer}"

Previous questions asked:
{previous_text}

Your job is to:

1. Briefly evaluate the candidate's answer.
2. Mention one strength.
3. Mention one improvement if necessary.
4. Ask exactly ONE next HR interview question.
5. Do not repeat any previous question.
6. Keep the question suitable for a college placement interview.
7. Be professional and encouraging.

Return ONLY valid JSON in this exact format:

{{
    "feedback": "Brief feedback about the candidate's answer",
    "next_question": "The next HR interview question"
}}
"""

    try:

        response = groq_client.chat.completions.create(
            model="openai/gpt-oss-120b",

            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a professional AI HR interviewer. "
                        "Return only valid JSON."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],

            temperature=0.7,
            max_completion_tokens=500,

            response_format={
                "type": "json_object"
            }
        )

        result = response.choices[0].message.content.strip()

        ai_result = json.loads(result)

        feedback = ai_result.get(
            "feedback",
            ""
        ).strip()

        next_question = ai_result.get(
            "next_question",
            ""
        ).strip()

        if not feedback:
            feedback = "Your answer has been evaluated successfully."

        if not next_question:
            return "Unable to generate next HR question.", 500

        # Save candidate answer
        interview_session["answers"].append(
            candidate_answer
        )

        # Save feedback
        interview_session["feedback"].append(
            feedback
        )

        # Save the NEW question
        interview_session["questions"].append(
            next_question
        )

        interview_session["question_number"] += 1

        hr_sessions[interview_type] = interview_session

        # IMPORTANT:
        # We DO NOT call url_for("hr_interview_next") here.
        # The feedback is displayed directly.

        return render_template(
            "hr_interview.html",

            interview_type=interview_type,

            interview_name=interview_name,

            question=next_question,

            feedback=feedback,

            answer=candidate_answer
        )

    except Exception as e:

        print("\n==============================")
        print("GROQ HR INTERVIEW ERROR")
        print(str(e))
        print("==============================\n")

        return (
            "Groq error: " + str(e),
            500
        )


# =========================================================
# HR INTERVIEW - MAIN PAGE
# =========================================================

@app.route("/hr/interview/<interview_type>")
def hr_interview(interview_type):

    allowed_types = {
        "basic": "Basic HR Interview",
        "placement": "Placement HR Interview",
        "situational": "Situational Interview"
    }

    if interview_type not in allowed_types:
        return "HR Interview type not found", 404

    # Create a fresh interview session
    hr_sessions[interview_type] = {
        "question_number": 0,
        "questions": [],
        "answers": [],
        "feedback": []
    }

    return render_template(
        "hr_interview.html",
        interview_type=interview_type,
        interview_name=allowed_types[interview_type],
        question=None,
        feedback=None,
        answer=None
    )


# =========================================================
# HR INTERVIEW - NEXT QUESTION
# =========================================================

@app.route("/hr/interview/<interview_type>/next")
def hr_interview_next(interview_type):

    allowed_types = {
        "basic": "Basic HR Interview",
        "placement": "Placement HR Interview",
        "situational": "Situational Interview"
    }

    if interview_type not in allowed_types:
        return "HR Interview type not found", 404

    interview_session = hr_sessions.get(
        interview_type
    )

    if not interview_session:
        return redirect(
            url_for(
                "hr_interview_start",
                interview_type=interview_type
            )
        )

    questions = interview_session.get(
        "questions",
        []
    )

    if not questions:
        return redirect(
            url_for(
                "hr_interview_start",
                interview_type=interview_type
            )
        )

    # The latest question was already generated
    # by the Submit Answer request.
    next_question = questions[-1]

    interview_name = allowed_types[interview_type]

    return render_template(
        "hr_interview.html",

        interview_type=interview_type,

        interview_name=interview_name,

        question=next_question,

        feedback=None,

        answer=None
    )


# =========================================================
# HR INTERVIEW - PREVIOUS QUESTION
# =========================================================

@app.route("/hr/interview/<interview_type>/previous")
def hr_interview_previous(interview_type):

    allowed_types = {
        "basic": "Basic HR Interview",
        "placement": "Placement HR Interview",
        "situational": "Situational Interview"
    }

    if interview_type not in allowed_types:
        return "HR Interview type not found", 404

    interview_session = hr_sessions.get(
        interview_type
    )

    if not interview_session:
        return redirect(
            url_for(
                "hr_interview_start",
                interview_type=interview_type
            )
        )

    questions = interview_session.get(
        "questions",
        []
    )

    if len(questions) <= 1:
        return redirect(
            url_for(
                "hr_interview_start",
                interview_type=interview_type
            )
        )

    # Go one question backward
    questions.pop()

    interview_session["questions"] = questions

    if interview_session["question_number"] > 1:
        interview_session["question_number"] -= 1

    hr_sessions[interview_type] = interview_session

    previous_question = questions[-1]

    return render_template(
        "hr_interview.html",

        interview_type=interview_type,

        interview_name=allowed_types[interview_type],

        question=previous_question,

        feedback=None,

        answer=None
    )
# =========================================================
# ===================== GD SECTION =========================
# =========================================================

# Make sure this exists ONCE somewhere above these routes:
# gd_sessions = {}


# =========================================================
# GD HOME
# =========================================================

@app.route("/gd")
def gd():
    return render_template("gd.html")


@app.route("/gd/topics")
def gd_topics():

    topics = [

        # ==============================
        # TECHNOLOGY & AI
        # ==============================

        "Artificial Intelligence: Boon or Bane?",
        "AI and Employment",
        "Will AI Replace Human Jobs?",
        "AI in Education",
        "Generative AI: Opportunity or Threat?",
        "Is Coding Necessary for Every Student?",
        "Technology and Human Creativity",
        "Impact of Automation on Jobs",
        "Robots vs Humans in the Workplace",
        "Future of Artificial Intelligence",
        "Cybersecurity in the Digital Age",
        "Data Privacy in the Digital World",
        "Social Media and Technology",
        "Digital India: Opportunities and Challenges",
        "Is Technology Making Us Smarter?",


        # ==============================
        # EDUCATION
        # ==============================

        "Online vs Offline Education",
        "Should College Education Be Skill-Based?",
        "Importance of Practical Education",
        "Are Marks More Important Than Skills?",
        "Skill-Based Education vs Degree-Based Education",
        "Should Coding Be Mandatory in Engineering?",
        "Role of Internships in College Education",
        "Is Online Learning Better Than Classroom Learning?",
        "Education System in India",
        "Importance of Communication Skills for Students",
        "Should Students Be Allowed to Use AI for Studies?",


        # ==============================
        # SOCIAL MEDIA
        # ==============================

        "Social Media: Boon or Bane?",
        "Impact of Social Media on Students",
        "Social Media and Mental Well-Being",
        "Should Social Media Have Age Restrictions?",
        "Influencers: Inspiration or Distraction?",
        "Social Media vs Traditional Media",
        "Is Social Media Reducing Face-to-Face Communication?",
        "Online Privacy vs Social Media Freedom",
        "Fake News and Social Media",
        "Short Videos: Entertainment or Addiction?",


        # ==============================
        # WORKPLACE & CAREER
        # ==============================

        "Work From Home vs Work From Office",
        "Work-Life Balance",
        "Startups vs Traditional Jobs",
        "Job Security vs High Salary",
        "Passion vs Salary: What Should Students Choose?",
        "Is Work-Life Balance Possible in Corporate Life?",
        "Importance of Teamwork in the Workplace",
        "Leadership vs Teamwork",
        "Technical Skills vs Soft Skills",
        "Communication Skills vs Technical Skills",
        "Should Companies Hire Based on Skills Instead of Degrees?",
        "Importance of Internships for Freshers",
        "Remote Work: Future of Employment?",
        "Four-Day Work Week",
        "Entrepreneurship vs Corporate Career",


        # ==============================
        # BUSINESS & ECONOMY
        # ==============================

        "Startups: Opportunity or Risk?",
        "Startup Culture in India",
        "Entrepreneurship Among Young Indians",
        "Make in India",
        "Digital Payments: Future of India",
        "Cashless Economy",
        "Online Shopping vs Traditional Shopping",
        "E-Commerce: Boon or Bane?",
        "Impact of Globalization on Indian Businesses",
        "Should India Become a Manufacturing Hub?",
        "Importance of Innovation in Business",
        "Small Businesses vs Large Corporations",


        # ==============================
        # ENVIRONMENT
        # ==============================

        "Climate Change and Its Impact",
        "Electric Vehicles: Future of Transportation?",
        "Electric Vehicles vs Petrol Vehicles",
        "Renewable Energy vs Conventional Energy",
        "Solar Energy: Future of India",
        "Environmental Protection vs Economic Growth",
        "Plastic Ban: Solution or Challenge?",
        "Sustainable Development",
        "Importance of Water Conservation",
        "Green Technology",
        "Can India Become Carbon Neutral?",
        "Role of Students in Protecting the Environment?",


        # ==============================
        # SOCIETY
        # ==============================

        "Gender Equality in the Workplace",
        "Women in Leadership",
        "Youth and Social Responsibility",
        "Importance of Volunteering",
        "Urbanization: Boon or Bane?",
        "Population Growth: Opportunity or Challenge?",
        "Brain Drain in India",
        "Generation Gap",
        "Workplace Diversity",
        "Equal Opportunities in Education",
        "Role of Youth in Nation Building",


        # ==============================
        # CURRENT / DEBATE STYLE TOPICS
        # ==============================

        "Is India Ready for the Future of Work?",
        "Can Technology Solve Social Problems?",
        "Is Economic Growth More Important Than Environmental Protection?",
        "Should Companies Prioritize Employee Well-Being?",
        "Are Smartphones Helping or Distracting Students?",
        "Is Artificial Intelligence the Biggest Technological Revolution?",
        "Can Machines Replace Human Creativity?",
        "Should Students Depend on AI Tools?",
        "Is Digital India Really Digital?",
        "Is Competition Good for Students?",
        "Should College Students Start Working Early?",
        "Is Failure Necessary for Success?",
        "Hard Work vs Smart Work",
        "Leadership: Born or Developed?",
        "Individual Success vs Team Success"

    ]

    return render_template(
        "gd_topics.html",
        topics=topics
    )


# =========================================================
# GD - AI CHOOSES TOPIC PAGE
# =========================================================

@app.route("/gd/ai-topic")
def gd_ai_topic():

    return render_template(
        "gd_ai_topic.html"
    )


# =========================================================
# GD - START DISCUSSION
# =========================================================

@app.route("/gd/start")
def gd_start():

    topic = request.args.get(
        "topic",
        ""
    ).strip()

    if not topic:
        return redirect(
            url_for("gd")
        )

    if groq_client is None:
        return (
            "GROQ_API_KEY is not configured.",
            500
        )

    # -----------------------------------------------------
    # Create a completely fresh GD session
    # -----------------------------------------------------

    gd_sessions[topic] = {

        "round": 1,

        "user_points": [],

        "participant1": "",
        "participant2": "",
        "participant3": "",

        "completed": False,

        "evaluation": None
    }

    session_data = gd_sessions[topic]

    # -----------------------------------------------------
    # Generate opening AI statements
    # -----------------------------------------------------

    prompt = f"""
You are conducting a college placement Group Discussion.

Topic:
{topic}

There are three AI participants.

Generate one short opening statement for each participant.

Participant 1:
Give a balanced perspective.

Participant 2:
Give a different perspective.

Participant 3:
Give another useful perspective.

Rules:
- Keep each response short.
- Use simple professional English.
- Do not speak for the candidate.
- Do not give feedback.
- Do not repeat the same idea.
- Return ONLY valid JSON.

JSON format:

{{
  "participant1": "short statement",
  "participant2": "short statement",
  "participant3": "short statement"
}}
"""

    try:

        response = groq_client.chat.completions.create(

            model="openai/gpt-oss-120b",

            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a professional "
                        "Group Discussion participant. "
                        "Return only valid JSON."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],

            temperature=0.7,

            max_completion_tokens=500,

            response_format={
                "type": "json_object"
            }
        )

        result = (
            response
            .choices[0]
            .message
            .content
            .strip()
        )

        data = json.loads(result)

        session_data["participant1"] = data.get(
            "participant1",
            ""
        ).strip()

        session_data["participant2"] = data.get(
            "participant2",
            ""
        ).strip()

        session_data["participant3"] = data.get(
            "participant3",
            ""
        ).strip()

        gd_sessions[topic] = session_data

        return render_template(

            "gd_discussion.html",

            topic=topic,

            participant1=session_data["participant1"],

            participant2=session_data["participant2"],

            participant3=session_data["participant3"],

            round_number=1,

            completed=False,

            evaluation=None,

            user_points=[]
        )

    except Exception as e:

        print("\n==============================")
        print("GD START ERROR")
        print(str(e))
        print("==============================\n")

        return (
            "Groq error: " + str(e),
            500
        )


# =========================================================
# GD - SUBMIT USER POINT
# =========================================================

@app.route(
    "/gd/room/submit",
    methods=["POST"]
)
def gd_room_submit():

    topic = request.form.get(
        "topic",
        ""
    ).strip()

    user_point = request.form.get(
        "user_point",
        ""
    ).strip()

    # -----------------------------------------------------
    # Basic validation
    # -----------------------------------------------------

    if not topic:
        return redirect(
            url_for("gd")
        )

    if not user_point:
        return redirect(
            url_for(
                "gd_start",
                topic=topic
            )
        )

    # -----------------------------------------------------
    # Check GD session
    # -----------------------------------------------------

    if topic not in gd_sessions:

        return redirect(
            url_for(
                "gd_start",
                topic=topic
            )
        )

    if groq_client is None:

        return (
            "GROQ_API_KEY is not configured.",
            500
        )

    session_data = gd_sessions[topic]

    # =====================================================
    # VERY IMPORTANT
    # IF GD IS COMPLETED, NEVER GENERATE ANOTHER ROUND
    # =====================================================

    if session_data.get(
        "completed",
        False
    ):

        return render_template(

            "gd_discussion.html",

            topic=topic,

            participant1=session_data.get(
                "participant1",
                ""
            ),

            participant2=session_data.get(
                "participant2",
                ""
            ),

            participant3=session_data.get(
                "participant3",
                ""
            ),

            round_number=5,

            completed=True,

            evaluation=session_data.get(
                "evaluation"
            ),

            user_points=session_data.get(
                "user_points",
                []
            )
        )

    # =====================================================
    # CURRENT ROUND
    # =====================================================

    current_round = len(
        session_data.get(
            "user_points",
            []
        )
    ) + 1

    # Safety limit
    if current_round > 5:

        return redirect(
            url_for(
                "gd_start",
                topic=topic
            )
        )

    # =====================================================
    # SAVE USER ANSWER
    # =====================================================

    session_data.setdefault(
        "user_points",
        []
    )

    session_data["user_points"].append(
        user_point
    )

    session_data["round"] = current_round

    gd_sessions[topic] = session_data

    # =====================================================
    # ⭐ ROUND 5 = FINAL ROUND
    # =====================================================

    if current_round == 5:

        all_answers = []

        for index, answer in enumerate(
            session_data["user_points"],
            start=1
        ):

            all_answers.append(
                f"Round {index}: {answer}"
            )

        all_answers_text = "\n".join(
            all_answers
        )

        # -------------------------------------------------
        # FINAL AI FEEDBACK PROMPT
        # -------------------------------------------------

        final_prompt = f"""
You are an expert college placement Group Discussion evaluator.

GD Topic:
{topic}

The candidate completed exactly five rounds.

Candidate responses:

{all_answers_text}

Evaluate ONLY the candidate's responses.

Give specific and encouraging feedback.

For every round provide:
- What was good.
- What should be improved.

Also provide scores from 1 to 10 for:
communication,
relevance,
content,
confidence,
clarity,
interaction,
overall.

Give:
- 3 strengths
- 3 improvements
- overall feedback
- practice advice

Return ONLY valid JSON.

Use EXACTLY this structure:

{{
  "round_feedback": [
    {{
      "round": 1,
      "what_was_good": "Specific feedback.",
      "what_to_improve": "Specific improvement."
    }},
    {{
      "round": 2,
      "what_was_good": "Specific feedback.",
      "what_to_improve": "Specific improvement."
    }},
    {{
      "round": 3,
      "what_was_good": "Specific feedback.",
      "what_to_improve": "Specific improvement."
    }},
    {{
      "round": 4,
      "what_was_good": "Specific feedback.",
      "what_to_improve": "Specific improvement."
    }},
    {{
      "round": 5,
      "what_was_good": "Specific feedback.",
      "what_to_improve": "Specific improvement."
    }}
  ],
  "communication": 0,
  "relevance": 0,
  "content": 0,
  "confidence": 0,
  "clarity": 0,
  "interaction": 0,
  "overall": 0,
  "strengths": [
    "Strength 1",
    "Strength 2",
    "Strength 3"
  ],
  "improvements": [
    "Improvement 1",
    "Improvement 2",
    "Improvement 3"
  ],
  "overall_feedback": "Overall evaluation.",
  "practice_advice": "Specific advice for future GDs."
}}
"""

        # -------------------------------------------------
        # GENERATE FINAL FEEDBACK
        # -------------------------------------------------

        try:

            

            response = groq_client.chat.completions.create(

                model="openai/gpt-oss-120b",

                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a professional "
                            "college placement GD evaluator. "
                            "Return only valid JSON."
                        )
                    },
                    {
                        "role": "user",
                        "content": final_prompt
                    }
                ],

                temperature=0.4,

                max_completion_tokens=1800,

                response_format={
                    "type": "json_object"
                }
            )

            result = (
                response
                .choices[0]
                .message
                .content
                .strip()
            )

            evaluation = json.loads(
                result
            )

            # -------------------------------------------------
            # ⭐ MARK SESSION AS COMPLETED
            # -------------------------------------------------

            session_data["completed"] = True

            session_data["evaluation"] = evaluation

            session_data["round"] = 5

            gd_sessions[topic] = session_data

            # -------------------------------------------------
            # SHOW FINAL FEEDBACK
            # -------------------------------------------------

            return render_template(

                "gd_discussion.html",

                topic=topic,

                participant1=session_data.get(
                    "participant1",
                    ""
                ),

                participant2=session_data.get(
                    "participant2",
                    ""
                ),

                participant3=session_data.get(
                    "participant3",
                    ""
                ),

                round_number=5,

                completed=True,

                evaluation=evaluation,

                user_points=session_data[
                    "user_points"
                ]
            )

        except Exception as e:

            print("\n==============================")
            print("GD FINAL FEEDBACK ERROR")
            print(str(e))
            print("==============================\n")

            return (
                "Groq error while generating "
                "GD feedback: " + str(e),
                500
            )

    # =====================================================
    # ROUNDS 1 - 4
    # =====================================================

    previous_answers = []

    for index, answer in enumerate(
        session_data["user_points"],
        start=1
    ):

        previous_answers.append(
            f"Round {index}: {answer}"
        )

    previous_answers_text = "\n".join(
        previous_answers
    )

    next_round = current_round + 1

    discussion_prompt = f"""
You are one of three AI participants in a college placement GD.

Topic:
{topic}

The candidate's latest answer:
{user_point}

Previous candidate answers:
{previous_answers_text}

This is round {next_round} of 5.

Generate one short response for each AI participant.

Rules:
- Each participant must have a different perspective.
- Respond naturally to the candidate.
- Do not repeat the same idea.
- Keep responses concise.
- Use professional English.
- Do not give feedback.
- Do not end the GD.
- Do not generate Round 6.
- Return ONLY valid JSON.

Format:

{{
  "participant1": "Response",
  "participant2": "Response",
  "participant3": "Response"
}}
"""

    try:

        response = groq_client.chat.completions.create(

            model="openai/gpt-oss-120b",

            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a realistic "
                        "Group Discussion participant. "
                        "Return only valid JSON."
                    )
                },
                {
                    "role": "user",
                    "content": discussion_prompt
                }
            ],

            temperature=0.7,

            max_completion_tokens=500,

            response_format={
                "type": "json_object"
            }
        )

        result = (
            response
            .choices[0]
            .message
            .content
            .strip()
        )

        data = json.loads(result)

        session_data["participant1"] = data.get(
            "participant1",
            session_data.get(
                "participant1",
                ""
            )
        ).strip()

        session_data["participant2"] = data.get(
            "participant2",
            session_data.get(
                "participant2",
                ""
            )
        ).strip()

        session_data["participant3"] = data.get(
            "participant3",
            session_data.get(
                "participant3",
                ""
            )
        ).strip()

        session_data["round"] = next_round

        gd_sessions[topic] = session_data

        return render_template(

            "gd_discussion.html",

            topic=topic,

            participant1=session_data[
                "participant1"
            ],

            participant2=session_data[
                "participant2"
            ],

            participant3=session_data[
                "participant3"
            ],

            round_number=next_round,

            completed=False,

            evaluation=None,

            user_points=session_data[
                "user_points"
            ]
        )

    except Exception as e:

        print("\n==============================")
        print("GD ROUND ERROR")
        print(str(e))
        print("==============================\n")

        return (
            "Groq error: " + str(e),
            500
        )

# =========================================================
# GD - AI GENERATE DIFFERENT PLACEMENT TOPIC
# =========================================================

@app.route("/gd/generate-topic")
def gd_generate_topic():

    if groq_client is None:

        return {
            "success": False,
            "error": "GROQ_API_KEY is not configured."
        }, 500


    # -----------------------------------------------------
    # PLACEMENT GD TOPIC POOL
    # -----------------------------------------------------

    placement_topics = [

        # ================= TECHNOLOGY & AI =================

        "Artificial Intelligence: Job Creator or Job Destroyer?",
        "Can AI Replace Human Creativity?",
        "Is Coding Still Necessary in the Age of AI?",
        "Should AI Be Regulated?",
        "AI in Education: Boon or Bane?",
        "Generative AI: Opportunity or Threat?",
        "Can AI Replace Freshers in IT Jobs?",
        "AI and the Future of Software Development",
        "Should Students Depend on AI Tools?",
        "Human Intelligence vs Artificial Intelligence",
        "Is Automation Good for Employment?",
        "Cybersecurity in the Age of AI",
        "Deepfakes and Misinformation",
        "Technology: Making Life Better or More Complicated?",
        "Will AI Reduce the Need for Human Workers?",


        # ================= EDUCATION =================

        "Skills vs Degree: What Matters More for Employment?",
        "Online Education vs Classroom Education",
        "Should Coding Be Taught in Schools?",
        "Is the Indian Education System Industry-Ready?",
        "Are College Grades More Important Than Skills?",
        "Should Internships Be Mandatory for Students?",
        "Does Practical Knowledge Matter More Than Theory?",
        "Is Digital Education the Future?",
        "Should Students Be Allowed to Use AI for Assignments?",
        "Education vs Employability",


        # ================= WORKPLACE =================

        "Work From Home vs Work From Office",
        "Is Work-Life Balance More Important Than Salary?",
        "Should Companies Adopt a Four-Day Work Week?",
        "Right to Disconnect: Should Employees Have It?",
        "Job Security vs High Salary",
        "Startup Job vs MNC Job",
        "Leadership vs Technical Skills",
        "Teamwork vs Individual Performance",
        "Should Companies Hire Based on Skills Instead of Degrees?",
        "Is Employee Monitoring Ethical?",


        # ================= BUSINESS & ECONOMY =================

        "Startups vs Traditional Jobs",
        "Entrepreneurship vs Job Security",
        "Can Startups Drive India's Economic Growth?",
        "Should India Focus More on Manufacturing?",
        "Digital Economy: Opportunity or Challenge?",
        "Cashless Economy: Benefits and Challenges",
        "Is Globalization Good for India?",
        "Profit vs Social Responsibility",
        "Should Companies Prioritize Employees or Customers?",
        "Small Businesses vs Large Corporations",


        # ================= SOCIAL MEDIA =================

        "Social Media: Boon or Bane?",
        "Should Social Media Be Regulated?",
        "Is Social Media Making People Less Social?",
        "Social Media Influencers: Career or Distraction?",
        "Digital Addiction Among Students",
        "Should Social Media Profiles Affect Hiring?",
        "Online Privacy vs Convenience",
        "Social Media and Mental Wellbeing",
        "Does Social Media Spread More Information or Misinformation?",
        "Is Influencer Marketing Ethical?",


        # ================= ENVIRONMENT =================

        "Electric Vehicles: Future of Transportation?",
        "Development vs Environmental Protection",
        "Climate Change: Individual or Government Responsibility?",
        "Renewable Energy vs Traditional Energy",
        "Sustainable Development vs Economic Growth",
        "Should Companies Be Responsible for Carbon Emissions?",
        "Is India Ready for Electric Vehicles?",
        "Green Technology and the Future",
        "Plastic Ban: Effective Solution or Temporary Measure?",
        "Can Economic Growth and Sustainability Go Together?",


        # ================= SOCIETY =================

        "Technology and Human Creativity",
        "Is Competition Always Healthy?",
        "Hard Work vs Smart Work",
        "Individual Freedom vs Social Responsibility",
        "Urbanization: Opportunity or Problem?",
        "Is Youth Participation Important in Nation Building?",
        "Should Companies Prioritize Diversity?",
        "Is Financial Literacy Important for Students?",
        "Success: Money or Job Satisfaction?",
        "Are Today's Students Too Dependent on Technology?",


        # ================= ABSTRACT / THINKING =================

        "Knowledge Is Power",
        "Failure Is the Stepping Stone to Success",
        "Hard Work Beats Talent",
        "Change Is the Only Constant",
        "Quality vs Quantity",
        "Experience vs Qualification",
        "Leadership Is More Important Than Authority",
        "Is Perfection the Enemy of Progress?",
        "Comfort Zone vs Growth",
        "Success Without Failure Is Possible"
    ]


    # -----------------------------------------------------
    # FIND PREVIOUSLY USED TOPICS
    # -----------------------------------------------------

    used_topics = gd_sessions.get(
        "_used_topics",
        []
    )


    # -----------------------------------------------------
    # ONLY SHOW UNUSED TOPICS
    # -----------------------------------------------------

    available_topics = [

        topic
        for topic in placement_topics
        if topic not in used_topics
    ]


    # -----------------------------------------------------
    # IF ALL TOPICS ARE USED
    # START AGAIN
    # -----------------------------------------------------

    if not available_topics:

        used_topics = []

        available_topics = placement_topics


    # -----------------------------------------------------
    # ASK AI TO SELECT ONE
    # -----------------------------------------------------

    topic_list = "\n".join(
        f"{i + 1}. {topic}"
        for i, topic in enumerate(
            available_topics
        )
    )


    prompt = f"""
You are a Group Discussion topic selector
for an engineering college placement preparation
platform in India.

Choose ONE topic from the list below.

These topics are specifically designed for
college placement GD practice.

TOPIC LIST:

{topic_list}

IMPORTANT RULES:

1. Choose ONLY ONE topic from the list.
2. Do not create a new topic.
3. Do not modify the topic.
4. Select a topic randomly.
5. Prefer topics suitable for IT and engineering
   placement GDs.
6. Do not always choose AI topics.
7. The topic should be different from previously
   selected topics.

Return ONLY valid JSON:

{{
    "topic": "exact topic from the list"
}}
"""


    try:

        response = groq_client.chat.completions.create(

            model="openai/gpt-oss-120b",

            messages=[

                {
                    "role": "system",
                    "content": (
                        "You are a professional "
                        "placement GD topic selector. "
                        "Return only valid JSON."
                    )
                },

                {
                    "role": "user",
                    "content": prompt
                }

            ],

            temperature=1.0,

            max_completion_tokens=100,

            response_format={
                "type": "json_object"
            }
        )


        result = (
            response
            .choices[0]
            .message
            .content
            .strip()
        )


        data = json.loads(result)


        topic = data.get(
            "topic",
            ""
        ).strip()


        # -------------------------------------------------
        # SAFETY CHECK
        # MAKE SURE AI SELECTED FROM OUR LIST
        # -------------------------------------------------

        if topic not in available_topics:

            import random

            topic = random.choice(
                available_topics
            )


        # -------------------------------------------------
        # SAVE TOPIC AS USED
        # -------------------------------------------------

        used_topics.append(topic)

        gd_sessions["_used_topics"] = used_topics


        return {

            "success": True,

            "topic": topic

        }


    except Exception as e:

        print(
            "\n=============================="
        )

        print(
            "GROQ GD TOPIC ERROR"
        )

        print(
            str(e)
        )

        print(
            "==============================\n"
        )


        # -------------------------------------------------
        # FALLBACK
        # EVEN IF GROQ FAILS, GIVE A DIFFERENT TOPIC
        # -------------------------------------------------

        import random

        topic = random.choice(
            available_topics
        )


        used_topics.append(topic)

        gd_sessions["_used_topics"] = used_topics


        return {

            "success": True,

            "topic": topic

        }

# =========================================================
# OPTIONAL OLD GD ROOM ROUTE
# =========================================================
# If any old button/link still uses /gd/room?topic=...
# send it to the SAME discussion system.

@app.route("/gd/room")
def gd_room():

    topic = request.args.get(
        "topic",
        ""
    ).strip()

    if not topic:
        return redirect(
            url_for("gd")
        )

    return redirect(
        url_for(
            "gd_start",
            topic=topic
        )
    )


# ============================================================
# AI INTERVIEW
# ============================================================
# AI INTERVIEW
# ============================================================

@app.route("/interview")
def interview():
    return render_template("interview.html")


# ============================================================
# START FRESH INTERVIEW
# ============================================================

@app.route("/interview/start")
def interview_start():

    # Start a completely fresh interview
    session["interview_scores"] = {
        "Aptitude": 0,
        "Coding": 0,
        "Technical": 0,
        "HR": 0,
        "Group Discussion": 0
    }

    session["interview_counts"] = {
        "Aptitude": 0,
        "Coding": 0,
        "Technical": 0,
        "HR": 0,
        "Group Discussion": 0
    }

    session["interview_completed"] = False

    return render_template("interview_start.html")


# ============================================================
# SUBMIT ANSWER
# ============================================================

@app.route("/interview/submit", methods=["POST"])
def interview_submit():

    data = request.get_json(silent=True) or {}

    answer = str(data.get("answer", "")).strip()
    round_name = str(data.get("round_name", "")).strip()
    question = str(data.get("question", "")).strip()


    # ========================================================
    # CHECK ANSWER
    # ========================================================

    if not answer:

        return jsonify({
            "success": False,
            "message": "Please select or enter your answer."
        }), 400


    # ========================================================
    # ANSWER KEYS
    # ========================================================

    aptitude_answers = {

        "A1": "B",
        "A2": "C",
        "A3": "A",
        "A4": "D",
        "A5": "B",
        "A6": "C",
        "A7": "A",
        "A8": "D",
        "A9": "B",
        "A10": "C"

    }


    coding_answers = {

        "C1": "B",
        "C2": "C",
        "C3": "A",
        "C4": "D",
        "C5": "B"

    }


    # ========================================================
    # GET SESSION DATA
    # ========================================================

    interview_scores = session.get(
        "interview_scores",
        {
            "Aptitude": 0,
            "Coding": 0,
            "Technical": 0,
            "HR": 0,
            "Group Discussion": 0
        }
    )

    interview_counts = session.get(
        "interview_counts",
        {
            "Aptitude": 0,
            "Coding": 0,
            "Technical": 0,
            "HR": 0,
            "Group Discussion": 0
        }
    )


    # ========================================================
    # APTITUDE MCQ
    # ========================================================

    if round_name == "Aptitude":

        correct_answer = aptitude_answers.get(question)

        if correct_answer is None:

            return jsonify({
                "success": False,
                "message": "Aptitude question not found."
            }), 400


        if answer.upper() == correct_answer:

            score = 10
            correct = True

            feedback = (
                "Correct! Excellent work. "
                "You selected the correct answer."
            )

            explanation = (
                "Your selected option is correct."
            )

        else:

            score = 0
            correct = False

            feedback = (
                "Incorrect answer. "
                "Review this concept and practice similar questions."
            )

            explanation = (
                f"The correct answer is option {correct_answer}."
            )


        interview_scores["Aptitude"] += score
        interview_counts["Aptitude"] += 1

        session["interview_scores"] = interview_scores
        session["interview_counts"] = interview_counts


        return jsonify({

            "success": True,
            "correct": correct,
            "score": score,
            "feedback": feedback,
            "explanation": explanation,

            # NO AI PARTICIPANTS IN APTITUDE
            "ai_participants": []

        })


    # ========================================================
    # CODING MCQ
    # ========================================================

    if round_name == "Coding":

        correct_answer = coding_answers.get(question)

        if correct_answer is None:

            return jsonify({
                "success": False,
                "message": "Coding question not found."
            }), 400


        if answer.upper() == correct_answer:

            score = 10
            correct = True

            feedback = (
                "Correct! Good understanding of "
                "the programming concept."
            )

            explanation = (
                "Your selected option is correct."
            )

        else:

            score = 0
            correct = False

            feedback = (
                "Incorrect answer. "
                "Review the programming concept "
                "and practice similar questions."
            )

            explanation = (
                f"The correct answer is option {correct_answer}."
            )


        interview_scores["Coding"] += score
        interview_counts["Coding"] += 1

        session["interview_scores"] = interview_scores
        session["interview_counts"] = interview_counts


        return jsonify({

            "success": True,
            "correct": correct,
            "score": score,
            "feedback": feedback,
            "explanation": explanation,

            # NO AI PARTICIPANTS IN CODING
            "ai_participants": []

        })


    # ========================================================
    # TECHNICAL / HR / GD
    # ========================================================

    word_count = len(answer.split())


    # ========================================================
    # TEXT ANSWER SCORE
    # ========================================================

    if word_count < 10:

        score = 5

        feedback = (
            "Your answer is a little short. "
            "Try to explain your thoughts in more detail."
        )


    elif word_count < 25:

        score = 7

        feedback = (
            "Good attempt. Add more explanation "
            "and specific examples to make your "
            "answer stronger."
        )


    else:

        score = 9

        feedback = (
            "Good answer. You explained your "
            "thoughts clearly. Try to keep your "
            "response structured and relevant."
        )


    # ========================================================
    # TECHNICAL FEEDBACK
    # ========================================================

    if round_name == "Technical":

        feedback += (
            " For technical questions, include "
            "a practical example whenever possible."
        )


    # ========================================================
    # HR FEEDBACK
    # ========================================================

    elif round_name == "HR":

        feedback += (
            " For HR questions, give specific examples "
            "from your academic, project or teamwork "
            "experience."
        )


    # ========================================================
    # GROUP DISCUSSION FEEDBACK
    # ========================================================

    elif round_name == "Group Discussion":

        feedback += (
            " In a GD, focus on relevant points, "
            "logical reasoning, clear communication "
            "and listening to other participants."
        )


    # ========================================================
    # AI PARTICIPANTS
    #
    # IMPORTANT:
    # ONLY GROUP DISCUSSION GETS 3 PARTICIPANTS
    # ========================================================

    ai_participants = []


    if round_name == "Group Discussion":

        ai_participants = [

            {
                "name": "AI Participant 1",
                "icon": "🤖",
                "response": (
                    "I believe this topic should be "
                    "considered from both positive "
                    "and negative perspectives."
                )
            },

            {
                "name": "AI Participant 2",
                "icon": "🤖",
                "response": (
                    "I agree with some points, but "
                    "there are also important challenges "
                    "that should be considered."
                )
            },

            {
                "name": "AI Industry Expert",
                "icon": "🤖",
                "response": (
                    "A strong discussion should use "
                    "logical reasoning, relevant examples "
                    "and clear communication."
                )
            }

        ]


    # ========================================================
    # SAVE TEXT ROUND SCORE
    # ========================================================

    if round_name in interview_scores:

        interview_scores[round_name] += score

        interview_counts[round_name] += 1

    else:

        interview_scores[round_name] = score
        interview_counts[round_name] = 1


    session["interview_scores"] = interview_scores
    session["interview_counts"] = interview_counts


    # ========================================================
    # RETURN RESULT
    # ========================================================

    return jsonify({

        "success": True,

        "correct": None,

        "score": score,

        "feedback": feedback,

        "explanation": "",

        "ai_participants": ai_participants

    })


# ============================================================
# FINAL AI INTERVIEW REPORT
# ============================================================

@app.route("/interview/report")
def interview_report():

    scores = session.get(
        "interview_scores",
        {}
    )


    # ========================================================
    # GET ROUND SCORES
    # ========================================================

    aptitude = scores.get("Aptitude", 0)

    coding = scores.get("Coding", 0)

    technical = scores.get("Technical", 0)

    hr = scores.get("HR", 0)

    gd = scores.get("Group Discussion", 0)


    # ========================================================
    # TOTAL SCORE
    # ========================================================

    total_score = (
        aptitude +
        coding +
        technical +
        hr +
        gd
    )


    # ========================================================
    # MAX SCORE
    #
    # 5 QUESTIONS PER ROUND
    #
    # Aptitude = 5 × 10 = 50
    # Coding   = 5 × 10 = 50
    # Technical = 5 × 9 = 45
    # HR        = 5 × 9 = 45
    # GD        = 5 × 9 = 45
    #
    # TOTAL = 235
    # ========================================================

    max_score = 235


    percentage = round(
        (total_score / max_score) * 100,
        1
    ) if max_score else 0


    # ========================================================
    # ROUND FEEDBACK
    # ========================================================

    round_feedback = {}


    # ========================================================
    # APTITUDE FEEDBACK
    # ========================================================

    if aptitude >= 40:

        round_feedback["Aptitude"] = (
            "Excellent aptitude performance. "
            "Your quantitative, logical and reasoning "
            "skills are strong."
        )

    elif aptitude >= 25:

        round_feedback["Aptitude"] = (
            "Good aptitude performance. "
            "Practice more numerical and reasoning "
            "questions to improve your accuracy."
        )

    else:

        round_feedback["Aptitude"] = (
            "Aptitude needs improvement. "
            "Focus on fundamentals and practice "
            "regularly."
        )


    # ========================================================
    # CODING FEEDBACK
    # ========================================================

    if coding >= 40:

        round_feedback["Coding"] = (
            "Excellent coding performance. "
            "Your programming fundamentals are strong."
        )

    elif coding >= 25:

        round_feedback["Coding"] = (
            "Good coding performance. "
            "Practice more programming concepts "
            "and problem-solving questions."
        )

    else:

        round_feedback["Coding"] = (
            "Coding needs improvement. "
            "Strengthen your programming fundamentals "
            "and practice regularly."
        )


    # ========================================================
    # TECHNICAL FEEDBACK
    # ========================================================

    if technical >= 36:

        round_feedback["Technical"] = (
            "Strong technical performance. "
            "You explained concepts clearly and "
            "showed good technical understanding."
        )

    elif technical >= 25:

        round_feedback["Technical"] = (
            "Good technical performance. "
            "Try to include more practical examples "
            "and explain concepts in greater depth."
        )

    else:

        round_feedback["Technical"] = (
            "Technical performance needs improvement. "
            "Revise important concepts and practice "
            "explaining technical topics clearly."
        )


    # ========================================================
    # HR FEEDBACK
    # ========================================================

    if hr >= 36:

        round_feedback["HR"] = (
            "Excellent HR performance. "
            "Your communication and confidence "
            "were strong."
        )

    elif hr >= 25:

        round_feedback["HR"] = (
            "Good HR performance. "
            "Try to use more specific examples "
            "from your academic or project experience."
        )

    else:

        round_feedback["HR"] = (
            "HR performance needs improvement. "
            "Work on confidence, communication "
            "and structuring your answers."
        )


    # ========================================================
    # GD FEEDBACK
    # ========================================================

    if gd >= 36:

        round_feedback["Group Discussion"] = (
            "Excellent GD performance. "
            "Your communication, reasoning and "
            "participation were strong."
        )

    elif gd >= 25:

        round_feedback["Group Discussion"] = (
            "Good GD performance. "
            "Focus on presenting clear points, "
            "logical reasoning and active listening."
        )

    else:

        round_feedback["Group Discussion"] = (
            "GD performance needs improvement. "
            "Practice expressing your ideas clearly, "
            "logically and confidently."
        )


    # ========================================================
    # OVERALL FEEDBACK
    # ========================================================

    if percentage >= 80:

        overall_feedback = (
            "Excellent overall performance! "
            "You appear well prepared for a placement interview."
        )

    elif percentage >= 60:

        overall_feedback = (
            "Good overall performance. "
            "You have a solid foundation, but some areas "
            "need additional practice."
        )

    elif percentage >= 40:

        overall_feedback = (
            "You have a good starting point, but you should "
            "spend more time strengthening your weaker rounds."
        )

    else:

        overall_feedback = (
            "More preparation is recommended. "
            "Focus on your fundamentals, communication "
            "and regular practice before attending a real interview."
        )


    # ========================================================
    # MARK INTERVIEW COMPLETED
    # ========================================================

    session["interview_completed"] = True


    # ========================================================
    # RETURN FINAL REPORT
    # ========================================================

    return jsonify({

        "success": True,

        "scores": {

            "Aptitude": aptitude,

            "Coding": coding,

            "Technical": technical,

            "HR": hr,

            "Group Discussion": gd

        },

        "total_score": total_score,

        "max_score": max_score,

        "percentage": percentage,

        "round_feedback": round_feedback,

        "overall_feedback": overall_feedback

    })


# ============================================================
# MY PROGRESS
# ============================================================

@app.route("/progress")
def progress():

    # Get saved interview scores
    interview_scores = session.get("interview_scores", {})

    aptitude = interview_scores.get("Aptitude", 0)
    coding = interview_scores.get("Coding", 0)
    technical = interview_scores.get("Technical", 0)
    hr = interview_scores.get("HR", 0)
    gd = interview_scores.get("Group Discussion", 0)

    # Maximum score for each round
    max_per_round = 50

    # Total score
    total_score = (
        aptitude +
        coding +
        technical +
        hr +
        gd
    )

    # Maximum total score
    max_score = 250

    # Percentage
    percentage = round(
        (total_score / max_score) * 100,
        1
    ) if max_score else 0

    # --------------------------------------------------------
    # COMPLETED ROUNDS
    # --------------------------------------------------------

    completed_rounds = sum([
        aptitude > 0,
        coding > 0,
        technical > 0,
        hr > 0,
        gd > 0
    ])

    # --------------------------------------------------------
    # ROUND STATUS
    # --------------------------------------------------------

    rounds = [

        {
            "name": "Aptitude",
            "icon": "🧮",
            "score": aptitude,
            "max_score": max_per_round,
            "completed": aptitude > 0
        },

        {
            "name": "Coding",
            "icon": "💻",
            "score": coding,
            "max_score": max_per_round,
            "completed": coding > 0
        },

        {
            "name": "Technical",
            "icon": "⚙️",
            "score": technical,
            "max_score": max_per_round,
            "completed": technical > 0
        },

        {
            "name": "HR Interview",
            "icon": "👤",
            "score": hr,
            "max_score": max_per_round,
            "completed": hr > 0
        },

        {
            "name": "Group Discussion",
            "icon": "🗣️",
            "score": gd,
            "max_score": max_per_round,
            "completed": gd > 0
        }

    ]

    # --------------------------------------------------------
    # RETURN PROGRESS PAGE
    # --------------------------------------------------------

    return render_template(
        "progress.html",

        rounds=rounds,

        aptitude=aptitude,
        coding=coding,
        technical=technical,
        hr=hr,
        gd=gd,

        total_score=total_score,
        max_score=max_score,
        percentage=percentage,

        completed_rounds=completed_rounds
    )





# ---------------- SETTINGS ----------------


@app.route("/settings")
def settings():

    return render_template("settings.html")







# ---------------- COMPANIES PAGE ----------------


@app.route("/companies")
def companies():


    companies = [


        {
            "name":"Google",
            "logo":"google.png"
        },


        {
            "name":"Microsoft",
            "logo":"microsoft.png"
        },


        {
            "name":"TCS",
            "logo":"tcs.png"
        },


        {
            "name":"Infosys",
            "logo":"infosys.jpg"
        },


        {
            "name":"Wipro",
            "logo":"wipro.jpg"
        },


        {
            "name":"Amazon",
            "logo":"amazon.jpg"
        },


        {
            "name":"Accenture",
            "logo":"accenture.jpg"
        },


        {
            "name":"IBM",
            "logo":"ibm.jpg"
        },


        {
            "name":"Cognizant",
            "logo":"cogzinant.jpg"
        },


        {
            "name":"Capgemini",
            "logo":"capgemini.jpg"
        },


        {
            "name":"Deloitte",
            "logo":"deloitte.jpg"
        },


        {
            "name":"Oracle",
            "logo":"oracle.jpg"
        }


    ]


    return render_template(

        "companies.html",

        companies=companies

    )







# ---------------- COMPANY DETAILS ----------------

company_logos = {

    "Google":"google.png",

    "Microsoft":"microsoft.png",

    "TCS":"tcs.png",

    "Infosys":"infosys.jpg",

    "Wipro":"wipro.jpg",

    "Amazon":"amazon.jpg",

    "Accenture":"accenture.jpg",

    "IBM":"ibm.jpg",

    "Cognizant":"cogzinant.jpg",

    "Capgemini":"capgemini.jpg",

    "Deloitte":"deloitte.jpg",

    "Oracle":"oracle.jpg"

}
@app.route("/company/<company_name>")
def company_details(company_name):


    company_data = {



        "Google":{


            "founded":"1998",

            "founder":"Larry Page and Sergey Brin",

            "leader":"Sundar Pichai (CEO)",

            "headquarters":"Mountain View, California, USA",


            "quote":"Organizing the world's information and making it universally accessible and useful.",

            "about":
            "Google is a global technology company specializing in search engine, AI, cloud computing and software products.",


            "roles":
            "Software Engineer, AI Engineer, Cloud Engineer",


            "skills":
            "Python, DSA, Machine Learning, Cloud, System Design",


            "rounds":
            "Online Assessment → Technical Interview → Googleyness/HR Round"


        },





        "Microsoft":{


            "founded":"1975",

            "founder":"Bill Gates and Paul Allen",

            "leader":"Satya Nadella (CEO)",

            "headquarters":"Redmond, Washington, USA",

            "quote":"Empowering every person and every organization on the planet to achieve more.",

            "about":
            "Microsoft develops software, cloud platforms and enterprise solutions.",


            "roles":
            "Software Developer, Cloud Engineer",


            "skills":
            "C++, Python, Azure, DSA",


            "rounds":
            "Coding Round → Technical Interview → HR Round"


        },





        "TCS":{


            "founded":"1968",

            "founder":"Tata Sons",

            "leader":"K. Krithivasan (CEO)",

            "headquarters":"Mumbai, India",

            "quote":"Building greater futures through innovation and technology.",

            "about":
            "TCS is a leading IT services and consulting company.",


            "roles":
            "Software Engineer, System Engineer",


            "skills":
            "Java, Python, SQL, Aptitude",


            "rounds":
            "Aptitude → Technical → HR"


        },





        "Infosys":{


            "founded":"1981",

            "founder":"N. R. Narayana Murthy and team",

            "leader":"Salil Parekh (CEO)",

            "headquarters":"Bengaluru, India",

            "quote":"Navigate your next with technology and innovation.",
            
            "about":
            "Infosys provides digital services, consulting and technology solutions.",


            "roles":
            "Systems Engineer, Developer",


            "skills":
            "Programming, Database, Communication",


            "rounds":
            "Online Test → Technical → HR"


        },





        "Amazon":{


            "founded":"1994",

            "founder":"Jeff Bezos",

            "leader":"Andy Jassy (CEO)",

            "headquarters":"Seattle, USA",

            "quote":"Work hard, have fun, and make history.",

            "about":
            "Amazon is a global e-commerce and cloud computing company.",


            "roles":
            "Software Development Engineer",


            "skills":
            "DSA, Algorithms, System Design",


            "rounds":
            "Online Assessment → Technical → HR"


        },
        "Accenture":{

"founded":"1989",

"founder":"Arthur Andersen",

"leader":"Julie Sweet (CEO)",

"headquarters":"Dublin, Ireland",

"quote":"Let there be change.",

"about":"Accenture is a global IT services and consulting company providing digital, cloud and security solutions.",

"roles":"Software Engineer, Cloud Engineer, Data Analyst",

"skills":"Python, Java, Cloud, SQL, Data Analytics",

"rounds":"Cognitive Assessment → Technical Interview → HR Interview"

},
"IBM":{

"founded":"1911",

"founder":"Charles Ranlett Flint",

"leader":"Arvind Krishna (CEO)",

"headquarters":"Armonk, New York, USA",

"quote":"Think. Innovate. Transform.",

"about":"IBM is a technology company focusing on cloud computing, AI and enterprise solutions.",

"roles":"Software Developer, AI Engineer, Cloud Engineer",

"skills":"Python, Java, AI, Cloud, Machine Learning",

"rounds":"Online Assessment → Technical Round → HR Round"

},
"Cognizant":{

"founded":"1994",

"founder":"Kumar Mahadeva and Francisco D'Souza",

"leader":"Ravi Kumar S (CEO)",

"headquarters":"Teaneck, New Jersey, USA",

"quote":"Engineering modern businesses with technology and innovation.",

"about":"Cognizant provides IT services, consulting and digital transformation solutions.",

"roles":"Programmer Analyst, Software Engineer",

"skills":"Java, Python, SQL, Cloud",

"rounds":"Aptitude → Technical → HR"

},
"Capgemini":{

"founded":"1967",

"founder":"Serge Kampf",

"leader":"Aiman Ezzat (CEO)",

"headquarters":"Paris, France",

"quote":"Get the future you want." ,

"about":"Capgemini is a global consulting and technology services company.",

"roles":"Software Engineer, Consultant",

"skills":"Java, Python, Cloud, Testing",

"rounds":"Online Test → Technical → HR"

},
"Deloitte":{

"founded":"1845",

"founder":"William Welch Deloitte",

"leader":"Jason Girzadas (CEO)",

"headquarters":"London, UK",

"quote":"Making an impact that matters.",

"about":"Deloitte provides consulting, auditing, financial and technology services.",

"roles":"Analyst, Technology Consultant",

"skills":"Data Analytics, Python, SQL, Cloud",

"rounds":"Aptitude → Technical → HR"

},
"Oracle":{

"founded":"1977",

"founder":"Larry Ellison, Bob Miner, Ed Oates",

"leader":"Safra Catz (CEO)",

"headquarters":"Austin, Texas, USA",

"quote":"Helping people see data in new ways, discover insights, and unlock possibilities.",

"about":"Oracle develops database software, cloud applications and enterprise technologies.",

"roles":"Database Engineer, Software Developer",

"skills":"SQL, Java, Database, Cloud",

"rounds":"Online Assessment → Technical → HR"

},
"Wipro":{

"founded":"1945",

"founder":"M. H. Hasham Premji",

"leader":"Srini Pallia (CEO)",

"headquarters":"Bengaluru, India",

"quote":"Spirit of Wipro: Be passionate about client success.",

"about":"Wipro is an IT services company providing technology consulting and digital solutions.",

"roles":"Software Engineer, Project Engineer",

"skills":"C, C++, Java, Python, SQL",

"rounds":"Online Test → Technical → HR"

}
        

    }



    company = company_data.get(company_name)


    return render_template(

        "company_details.html",

        company=company,

        name=company_name,

        logo=company_logos.get(company_name)

    )




@app.route("/ai_questions/<company>")
def ai_questions(company):

    questions = generate_questions(company)

    formatted_questions = markdown.markdown(
    questions,
    extensions=["tables"]
)


    return render_template(
        "ai_questions.html",
        company=company,
        questions=formatted_questions
    )
# ---------------- RUN ----------------

@app.route('/learn/coding_decoding')
def coding_decoding():
    return render_template('coding_decoding.html')


@app.route('/learn/number_series')
def number_series():
    return render_template('number_series.html')


@app.route('/learn/letter_series')
def letter_series():
    return render_template('letter_series.html')



# ==========================================
# AI PRACTICE MCQ
# ==========================================

practice_questions = {

    "quantitative": [],

    "logical": [],

    "verbal": []

}


practice_index = {

    "quantitative": 0,

    "logical": 0,

    "verbal": 0

}


# ==========================================
# QUANTITATIVE PRACTICE
# ==========================================

@app.route("/practice/quantitative")
def quantitative_practice():

    section_key = "quantitative"

    topics = [

        "Number System",
        "Percentage",
        "Profit and Loss",
        "Time and Work",
        "Probability",
        "Ratio and Proportion",
        "Average",
        "Simple Interest",
        "Compound Interest",
        "Time Speed and Distance",
        "Permutation and Combination",
        "Data Interpretation",
        "Simplification and Approximation",
        "Algebra",
        "Mixtures",
        "Pipes and Cisterns",
        "Partnership",
        "HCF and LCM",
        "Ages",
        "Sequence and Series"

    ]

    question = generate_mcq(
        "Quantitative Aptitude",
        topics
    )

    practice_questions[section_key] = [question]

    practice_index[section_key] = 0

    return render_template(

        "practice_mcq.html",

        section="Quantitative Aptitude",

        section_key=section_key,

        question=question,

        question_number=1,

        syllabus_url=url_for("quantitative")

    )


# ==========================================
# LOGICAL PRACTICE
# ==========================================

@app.route("/practice/logical")
def logical_practice():

    section_key = "logical"

    topics = [

        "Coding and Decoding",
        "Number Series",
        "Letter Series",
        "Blood Relations",
        "Direction Sense",
        "Seating Arrangement",
        "Syllogism",
        "Venn Diagram",
        "Statement and Conclusion",
        "Data Sufficiency",
        "Analogy",
        "Classification"

    ]

    question = generate_mcq(

        "Logical Reasoning",

        topics

    )

    practice_questions[section_key] = [question]

    practice_index[section_key] = 0

    return render_template(

        "practice_mcq.html",

        section="Logical Reasoning",

        section_key=section_key,

        question=question,

        question_number=1,

        syllabus_url=url_for("logical")

    )


# ==========================================
# VERBAL PRACTICE
# ==========================================

@app.route("/practice/verbal")
def verbal_practice():

    section_key = "verbal"

    topics = [

        "Parts of Speech",
        "Articles",
        "Tenses",
        "Spelling",
        "Reading Comprehension",
        "Sentence Correction",
        "Para Jumbles",
        "Cloze Test"

    ]

    question = generate_mcq(

        "Verbal Ability",

        topics

    )

    practice_questions[section_key] = [question]

    practice_index[section_key] = 0

    return render_template(

        "practice_mcq.html",

        section="Verbal Ability",

        section_key=section_key,

        question=question,

        question_number=1,

        syllabus_url=url_for("verbal")

    )

# ==========================================
# NEXT QUESTION
# ==========================================

@app.route("/practice/<section_key>/next")
def next_question(section_key):

    topics = {
        "quantitative": [
            "Number System",
            "Percentage",
            "Profit and Loss",
            "Time and Work",
            "Probability",
            "Ratio and Proportion",
            "Average",
            "Simple Interest",
            "Compound Interest",
            "Time Speed and Distance",
            "Permutation and Combination",
            "Data Interpretation",
            "Simplification and Approximation",
            "Algebra",
            "Mixtures",
            "Pipes and Cisterns",
            "Partnership",
            "HCF and LCM",
            "Ages",
            "Sequence and Series"
        ],

        "logical": [
            "Coding and Decoding",
            "Number Series",
            "Letter Series",
            "Blood Relations",
            "Direction Sense",
            "Seating Arrangement",
            "Syllogism",
            "Venn Diagram",
            "Statement and Conclusion",
            "Data Sufficiency",
            "Analogy",
            "Classification"
        ],

        "verbal": [
            "Parts of Speech",
            "Articles",
            "Tenses",
            "Spelling",
            "Reading Comprehension",
            "Sentence Correction",
            "Para Jumbles",
            "Cloze Test"
        ]
    }

    section_names = {
        "quantitative": "Quantitative Aptitude",
        "logical": "Logical Reasoning",
        "verbal": "Verbal Ability"
    }

    # Check section
    if section_key not in topics:
        return "Invalid practice section", 404

    # Make sure the section exists
    if section_key not in practice_questions:
        practice_questions[section_key] = []

    if section_key not in practice_index:
        practice_index[section_key] = 0

    # Generate new question
    question = generate_mcq(
        section_names[section_key],
        topics[section_key]
    )

    # Store question
    practice_questions[section_key].append(question)

    # Move index forward
    practice_index[section_key] += 1

    question_number = practice_index[section_key] + 1

    # Correct syllabus endpoint
    syllabus_endpoints = {
        "quantitative": "quantitative",
        "logical": "logical",
        "verbal": "verbal"
    }

    return render_template(
        "practice_mcq.html",

        section=section_names[section_key],

        section_key=section_key,

        question=question,

        question_number=question_number,

        syllabus_url=url_for(
            syllabus_endpoints[section_key]
        )
    )
# ==========================================
# PREVIOUS QUESTION
# ==========================================

@app.route("/practice/<section_key>/previous")
def previous_question(section_key):

    section_names = {
        "quantitative": "Quantitative Aptitude",
        "logical": "Logical Reasoning",
        "verbal": "Verbal Ability"
    }

    syllabus_endpoints = {
        "quantitative": "quantitative",
        "logical": "logical",
        "verbal": "verbal"
    }

    # Check section
    if section_key not in practice_questions:
        return "Invalid practice section", 404

    # Check index
    if section_key not in practice_index:
        practice_index[section_key] = 0

    # Don't go before first question
    if practice_index[section_key] > 0:
        practice_index[section_key] -= 1

    current_index = practice_index[section_key]

    question = practice_questions[section_key][current_index]

    question_number = current_index + 1

    return render_template(
        "practice_mcq.html",

        section=section_names[section_key],

        section_key=section_key,

        question=question,

        question_number=question_number,

        syllabus_url=url_for(
            syllabus_endpoints[section_key]
        )
    )
# ---------------- MCQ PRACTICE ----------------

practice_questions = {
    "quantitative": [
        {
            "question": "What is 20% of 250?",
            "options": ["40", "50", "60", "70"],
            "answer": "50",
            "explanation": "20% of 250 = (20/100) × 250 = 50."
        },
        {
            "question": "If the ratio of boys to girls is 2:3 and there are 20 boys, how many girls are there?",
            "options": ["25", "30", "35", "40"],
            "answer": "30",
            "explanation": "2 parts = 20, so 1 part = 10. Therefore 3 parts = 30."
        }
    ],

    "logical": [
        {
            "question": "Find the next number: 2, 4, 8, 16, ?",
            "options": ["20", "24", "32", "36"],
            "answer": "32",
            "explanation": "Each number is multiplied by 2. Therefore, 16 × 2 = 32."
        },
        {
            "question": "If A is the brother of B and B is the sister of C, how is A related to C?",
            "options": ["Brother", "Sister", "Father", "Mother"],
            "answer": "Brother",
            "explanation": "A is the brother of B, and B is the sister of C. Therefore A is C's brother."
        }
    ],

    "verbal": [
        {
            "question": "Choose the correct synonym of 'Happy'.",
            "options": ["Sad", "Joyful", "Angry", "Weak"],
            "answer": "Joyful",
            "explanation": "Joyful means feeling or expressing happiness."
        },
        {
            "question": "Choose the correct sentence.",
            "options": [
                "She go to college.",
                "She going to college.",
                "She goes to college.",
                "She gone to college."
            ],
            "answer": "She goes to college.",
            "explanation": "With the singular subject 'She', the correct present-tense verb is 'goes'."
        }
    ]
}


@app.route("/practice/<section>")
def practice_mcq(section):

    # Make sure the section is valid
    if section not in practice_questions:
        return "Invalid practice section", 404

    # Start from first question
    question = practice_questions[section][0]

    return render_template(
        "practice_mcq.html",
        section=section,
        question=question,
        question_number=1,
        total_questions=len(practice_questions[section])
    )


@app.route("/coding/python")
def coding_python():
    return render_template("coding_python.html")


@app.route("/coding/python/learn")
def python_learn():
    return render_template("python_learn.html", topic=None)


@app.route("/coding/python/learn/<topic>")
def python_learn_topic(topic):

    valid_topics = [
        "basics",
        "variables",
        "operators",
        "conditions",
        "loops",
        "functions",
        "lists",
        "tuples",
        "sets",
        "dictionaries",
        "strings",
        "exceptions",
        "files",
        "oops",
        "modules",
        "problem-solving"
    ]

    if topic not in valid_topics:
        return "Topic not found", 404

    return render_template(
        "python_learn.html",
        topic=topic
    )



@app.route("/coding/javascript/learn/")
@app.route("/coding/javascript/learn/<topic>")
def javascript_learn_topic(topic=None):

    valid_topics = [
        "basics",
        "variables",
        "operators",
        "conditions",
        "loops",
        "functions",
        "arrays",
        "strings",
        "objects",
        "dom",
        "events",
        "es6",
        "json",
        "async",
        "error-handling",
        "problem-solving"
    ]

    if topic is not None and topic not in valid_topics:
        return "Topic not found", 404

    return render_template(
        "javascript_learn.html",
        topic=topic
    )

@app.route("/coding/react/learn/")
@app.route("/coding/react/learn/<topic>")
def react_learn_topic(topic=None):

    valid_topics = [
        "basics",
        "jsx",
        "components",
        "props",
        "state",
        "events",
        "conditional-rendering",
        "lists",
        "forms",
        "hooks",
        "usestate",
        "useeffect",
        "routing",
        "api",
        "project-structure",
        "problem-solving"
    ]

    if topic is not None and topic not in valid_topics:
        return "Topic not found", 404

    return render_template(
        "react_learn.html",
        topic=topic
    )

@app.route("/coding/java/learn")
def java_learn():

    return render_template(
        "java_learn.html",
        topic=None
    )


@app.route("/coding/java/learn/<topic>")
def java_learn_topic(topic):

    valid_topics = [
        "basics",
        "variables",
        "operators",
        "conditions",
        "loops",
        "methods",
        "arrays",
        "strings",
        "classes",
        "inheritance",
        "polymorphism",
        "interfaces",
        "collections",
        "exception",
        "file-handling",
        "problem-solving"
    ]

    if topic not in valid_topics:
        return "Topic not found", 404

    return render_template(
        "java_learn.html",
        topic=topic
    )


@app.route("/coding/cpp/learn")
def cpp_learn():

    return render_template(
        "cpp_learn.html",
        topic=None
    )


@app.route("/coding/cpp/learn/<topic>")
def cpp_learn_topic(topic):

    valid_topics = [
        "basics",
        "variables",
        "operators",
        "conditions",
        "loops",
        "functions",
        "arrays",
        "strings",
        "pointers",
        "classes",
        "inheritance",
        "polymorphism",
        "stl",
        "exception",
        "file-handling",
        "problem-solving"
    ]

    if topic not in valid_topics:
        return "Topic not found", 404

    return render_template(
        "cpp_learn.html",
        topic=topic
    )


@app.route("/coding/c/learn")
def c_learn():

    return render_template(
        "c_learn.html",
        topic=None
    )


@app.route("/coding/c/learn/<topic>")
def c_learn_topic(topic):

    valid_topics = [
        "basics",
        "variables",
        "operators",
        "conditions",
        "loops",
        "functions",
        "arrays",
        "strings",
        "pointers",
        "structures",
        "unions",
        "memory",
        "files",
        "preprocessor",
        "recursion",
        "problem-solving"
    ]

    if topic not in valid_topics:
        return "Topic not found", 404

    return render_template(
        "c_learn.html",
        topic=topic
    )



@app.route("/coding/c")
def coding_c():
    return render_template("coding_c.html")


@app.route("/coding/cpp")
def coding_cpp():
    return render_template("coding_cpp.html")


@app.route("/coding/java")
def coding_java():
    return render_template("coding_java.html")


@app.route("/coding/javascript")
def coding_javascript():
    return render_template("coding_javascript.html")


@app.route("/coding/react")
def coding_react():
    return render_template("coding_react.html")

# ============================================================
# CODING PRACTICE QUESTIONS
# ============================================================

coding_questions = {

    "python": [
        {
            "topic": "Python Basics",
            "question": "Which keyword is used to define a function in Python?",
            "options": ["function", "def", "define", "fun"],
            "answer": "def",
            "explanation": "The def keyword is used to define a function in Python."
        },
        {
            "topic": "Python Variables",
            "question": "Which of the following is a valid Python variable name?",
            "options": ["2name", "my_name", "my-name", "class"],
            "answer": "my_name",
            "explanation": "Python variable names can contain letters, numbers and underscores, but cannot start with a number."
        },
        {
            "topic": "Python Loops",
            "question": "Which loop is commonly used to iterate through a sequence in Python?",
            "options": ["for", "repeat", "loop", "iterate"],
            "answer": "for",
            "explanation": "The for loop is commonly used to iterate through sequences."
        },
        {
            "topic": "Python Lists",
            "question": "Which symbol is used to create a list in Python?",
            "options": ["()", "{}", "[]", "<>"],
            "answer": "[]",
            "explanation": "Python lists are created using square brackets."
        },
        {
            "topic": "Python Data Types",
            "question": "Which data type is used to store True or False values?",
            "options": ["int", "str", "bool", "float"],
            "answer": "bool",
            "explanation": "The bool data type stores True or False values."
        },
        {
            "topic": "Python Strings",
            "question": "Which function is used to find the length of a string?",
            "options": ["size()", "length()", "len()", "count()"],
            "answer": "len()",
            "explanation": "The len() function returns the number of characters in a string."
        },
        {
            "topic": "Python Conditions",
            "question": "Which keyword is used to check a condition in Python?",
            "options": ["check", "if", "when", "condition"],
            "answer": "if",
            "explanation": "The if keyword is used for conditional execution."
        },
        {
            "topic": "Python Tuples",
            "question": "Which brackets are commonly used to create a tuple?",
            "options": ["[]", "{}", "()", "<>"],
            "answer": "()",
            "explanation": "Tuples are commonly written using parentheses."
        },
        {
            "topic": "Python Dictionaries",
            "question": "Which data structure stores data as key-value pairs?",
            "options": ["List", "Tuple", "Dictionary", "Set"],
            "answer": "Dictionary",
            "explanation": "A dictionary stores data using key-value pairs."
        },
        {
            "topic": "Python OOP",
            "question": "Which keyword is used to create a class in Python?",
            "options": ["object", "class", "struct", "define"],
            "answer": "class",
            "explanation": "The class keyword is used to define a class."
        }
    ],

    "c": [
        {
            "topic": "C Basics",
            "question": "Which function is the starting point of a C program?",
            "options": ["start()", "main()", "begin()", "run()"],
            "answer": "main()",
            "explanation": "Execution of a C program begins from main()."
        },
        {
            "topic": "C Variables",
            "question": "Which data type is commonly used to store an integer in C?",
            "options": ["float", "char", "int", "double"],
            "answer": "int",
            "explanation": "The int data type stores integer values."
        },
        {
            "topic": "C Loops",
            "question": "Which loop is commonly used when the number of iterations is known?",
            "options": ["if", "for", "switch", "goto"],
            "answer": "for",
            "explanation": "The for loop is commonly used when the number of iterations is known."
        },
        {
            "topic": "C Arrays",
            "question": "What is the index of the first element of an array in C?",
            "options": ["0", "1", "-1", "2"],
            "answer": "0",
            "explanation": "C arrays use zero-based indexing."
        },
        {
            "topic": "C Pointers",
            "question": "Which symbol is used to declare a pointer in C?",
            "options": ["&", "*", "#", "%"],
            "answer": "*",
            "explanation": "The * symbol is used when declaring a pointer."
        },
        {
            "topic": "C Strings",
            "question": "Which character marks the end of a C string?",
            "options": ["\\n", "\\0", "\\t", "\\s"],
            "answer": "\\0",
            "explanation": "C strings end with the null character \\0."
        },
        {
            "topic": "C Conditions",
            "question": "Which statement is used for decision making in C?",
            "options": ["if", "loop", "repeat", "define"],
            "answer": "if",
            "explanation": "The if statement is used for conditional execution."
        },
        {
            "topic": "C Structures",
            "question": "Which keyword is used to define a structure in C?",
            "options": ["structure", "struct", "record", "class"],
            "answer": "struct",
            "explanation": "The struct keyword is used to define a structure."
        },
        {
            "topic": "C Functions",
            "question": "Which keyword is used to return a value from a function?",
            "options": ["return", "send", "output", "back"],
            "answer": "return",
            "explanation": "The return statement sends a value back from a function."
        },
        {
            "topic": "C Preprocessor",
            "question": "Which symbol begins a preprocessor directive in C?",
            "options": ["@", "#", "$", "&"],
            "answer": "#",
            "explanation": "C preprocessor directives begin with #."
        }
    ],

    "cpp": [
        {
            "topic": "C++ Basics",
            "question": "Which symbol is used to end most statements in C++?",
            "options": [".", ":", ";", ","],
            "answer": ";",
            "explanation": "Most C++ statements end with a semicolon."
        },
        {
            "topic": "C++ OOP",
            "question": "Which concept allows a class to acquire properties of another class?",
            "options": ["Encapsulation", "Inheritance", "Compilation", "Iteration"],
            "answer": "Inheritance",
            "explanation": "Inheritance allows one class to acquire properties of another."
        },
        {
            "topic": "C++ Classes",
            "question": "Which keyword is used to create a class in C++?",
            "options": ["object", "class", "structural", "define"],
            "answer": "class",
            "explanation": "The class keyword defines a class."
        },
        {
            "topic": "C++ Loops",
            "question": "Which loop executes while a condition remains true?",
            "options": ["while", "switch", "if", "case"],
            "answer": "while",
            "explanation": "The while loop executes repeatedly while its condition is true."
        },
        {
            "topic": "C++ Constructors",
            "question": "What is a constructor in C++?",
            "options": [
                "A special member function",
                "A loop",
                "A variable",
                "A header file"
            ],
            "answer": "A special member function",
            "explanation": "A constructor is a special member function used to initialize objects."
        },
        {
            "topic": "C++ Polymorphism",
            "question": "Which concept allows the same function name to behave differently?",
            "options": ["Polymorphism", "Inheritance", "Compilation", "Iteration"],
            "answer": "Polymorphism",
            "explanation": "Polymorphism allows one interface to represent different implementations."
        },
        {
            "topic": "C++ Pointers",
            "question": "Which operator is used to obtain the address of a variable?",
            "options": ["*", "&", "#", "%"],
            "answer": "&",
            "explanation": "The & operator gives the memory address of a variable."
        },
        {
            "topic": "C++ STL",
            "question": "Which STL container stores elements in a dynamic array?",
            "options": ["vector", "stack", "queue", "map"],
            "answer": "vector",
            "explanation": "vector is a dynamic array container in the C++ STL."
        },
        {
            "topic": "C++ Inheritance",
            "question": "Which access specifier allows members to be accessed by derived classes?",
            "options": ["private", "protected", "hidden", "internal"],
            "answer": "protected",
            "explanation": "Protected members can be accessed by the class and its derived classes."
        },
        {
            "topic": "C++ Functions",
            "question": "What is function overloading?",
            "options": [
                "Using multiple functions with the same name but different parameters",
                "Deleting a function",
                "Calling a function once",
                "Creating a variable"
            ],
            "answer": "Using multiple functions with the same name but different parameters",
            "explanation": "Function overloading allows multiple functions with the same name and different parameter lists."
        }
    ],

    "java": [
        {
            "topic": "Java Basics",
            "question": "Which method is the starting point of a Java application?",
            "options": ["start()", "main()", "run()", "execute()"],
            "answer": "main()",
            "explanation": "Java applications normally begin execution from main()."
        },
        {
            "topic": "Java Variables",
            "question": "Which data type is used to store whole numbers in Java?",
            "options": ["double", "String", "int", "boolean"],
            "answer": "int",
            "explanation": "int is commonly used for whole numbers."
        },
        {
            "topic": "Java OOP",
            "question": "Which keyword is used for inheritance in Java?",
            "options": ["inherit", "extends", "inherits", "using"],
            "answer": "extends",
            "explanation": "The extends keyword is used for class inheritance."
        },
        {
            "topic": "Java Exceptions",
            "question": "Which block is used to handle an exception in Java?",
            "options": ["if", "catch", "switch", "handle"],
            "answer": "catch",
            "explanation": "The catch block handles exceptions."
        },
        {
            "topic": "Java Classes",
            "question": "Which keyword is used to create a class in Java?",
            "options": ["class", "object", "define", "struct"],
            "answer": "class",
            "explanation": "The class keyword defines a Java class."
        },
        {
            "topic": "Java Interfaces",
            "question": "Which keyword is used to define an interface in Java?",
            "options": ["interface", "implements", "abstract", "protocol"],
            "answer": "interface",
            "explanation": "The interface keyword defines an interface."
        },
        {
            "topic": "Java Arrays",
            "question": "What is the first index of an array in Java?",
            "options": ["0", "1", "-1", "2"],
            "answer": "0",
            "explanation": "Java arrays use zero-based indexing."
        },
        {
            "topic": "Java Strings",
            "question": "Which class represents strings in Java?",
            "options": ["Text", "String", "Char", "StringData"],
            "answer": "String",
            "explanation": "The String class represents sequences of characters."
        },
        {
            "topic": "Java Loops",
            "question": "Which loop is commonly used to iterate through an array?",
            "options": ["for", "switch", "if", "catch"],
            "answer": "for",
            "explanation": "A for loop is commonly used to iterate through arrays."
        },
        {
            "topic": "Java Collections",
            "question": "Which collection stores elements as key-value pairs?",
            "options": ["ArrayList", "HashMap", "Stack", "Queue"],
            "answer": "HashMap",
            "explanation": "HashMap stores data as key-value pairs."
        }
    ],

    "javascript": [
        {
            "topic": "JavaScript Basics",
            "question": "Which keyword can be used to declare a variable in JavaScript?",
            "options": ["let", "define", "variable", "integer"],
            "answer": "let",
            "explanation": "let declares a block-scoped variable."
        },
        {
            "topic": "JavaScript Functions",
            "question": "Which keyword is commonly used to declare a function?",
            "options": ["def", "function", "fun", "method"],
            "answer": "function",
            "explanation": "The function keyword declares a function."
        },
        {
            "topic": "JavaScript Arrays",
            "question": "Which brackets are used to create an array?",
            "options": ["()", "{}", "[]", "<>"],
            "answer": "[]",
            "explanation": "JavaScript arrays use square brackets."
        },
        {
            "topic": "JavaScript Conditions",
            "question": "Which statement is used for decision making?",
            "options": ["if", "repeat", "loop", "define"],
            "answer": "if",
            "explanation": "The if statement performs conditional execution."
        },
        {
            "topic": "JavaScript Constants",
            "question": "Which keyword declares a constant variable?",
            "options": ["const", "constant", "fixed", "static"],
            "answer": "const",
            "explanation": "The const keyword declares a variable that cannot be reassigned."
        },
        {
            "topic": "JavaScript Objects",
            "question": "Which brackets are commonly used to define an object?",
            "options": ["[]", "{}", "()", "<>"],
            "answer": "{}",
            "explanation": "JavaScript objects are commonly created using curly braces."
        },
        {
            "topic": "JavaScript DOM",
            "question": "What does DOM stand for?",
            "options": [
                "Document Object Model",
                "Data Object Management",
                "Digital Object Model",
                "Document Order Method"
            ],
            "answer": "Document Object Model",
            "explanation": "DOM stands for Document Object Model."
        },
        {
            "topic": "JavaScript Events",
            "question": "Which event occurs when a user clicks an element?",
            "options": ["onclick", "onload", "onchange", "onsubmit"],
            "answer": "onclick",
            "explanation": "The onclick event occurs when an element is clicked."
        },
        {
            "topic": "JavaScript ES6",
            "question": "Which feature was introduced with ES6?",
            "options": ["let and const", "printf", "pointers", "classes in C"],
            "answer": "let and const",
            "explanation": "ES6 introduced let and const among many other features."
        },
        {
            "topic": "JavaScript JSON",
            "question": "What does JSON stand for?",
            "options": [
                "JavaScript Object Notation",
                "Java Source Object Network",
                "JavaScript Online Network",
                "JSON Object Name"
            ],
            "answer": "JavaScript Object Notation",
            "explanation": "JSON stands for JavaScript Object Notation."
        }
    ],

    "react": [
        {
            "topic": "React Basics",
            "question": "What is React mainly used for?",
            "options": [
                "Building user interfaces",
                "Managing databases",
                "Operating systems",
                "Writing SQL queries"
            ],
            "answer": "Building user interfaces",
            "explanation": "React is mainly used to build user interfaces."
        },
        {
            "topic": "React Components",
            "question": "What is a React component?",
            "options": [
                "A reusable UI building block",
                "A database table",
                "A CSS file only",
                "A server"
            ],
            "answer": "A reusable UI building block",
            "explanation": "Components are reusable building blocks of React applications."
        },
        {
            "topic": "React JSX",
            "question": "What does JSX allow developers to write?",
            "options": [
                "HTML-like syntax inside JavaScript",
                "SQL inside CSS",
                "Python inside HTML",
                "Java inside SQL"
            ],
            "answer": "HTML-like syntax inside JavaScript",
            "explanation": "JSX allows HTML-like syntax to be written inside JavaScript."
        },
        {
            "topic": "React State",
            "question": "Which React Hook is commonly used to manage component state?",
            "options": ["useState", "useHTML", "useCSS", "useDatabase"],
            "answer": "useState",
            "explanation": "useState is used to manage state in function components."
        },
        {
            "topic": "React Effects",
            "question": "Which Hook is commonly used for side effects?",
            "options": ["useEffect", "useSide", "useAction", "useEvent"],
            "answer": "useEffect",
            "explanation": "useEffect is commonly used for side effects."
        },
        {
            "topic": "React Props",
            "question": "What are props used for in React?",
            "options": [
                "Passing data to components",
                "Creating databases",
                "Styling only",
                "Compiling JavaScript"
            ],
            "answer": "Passing data to components",
            "explanation": "Props are used to pass data from one component to another."
        },
        {
            "topic": "React Lists",
            "question": "Which JavaScript method is commonly used to render a list in React?",
            "options": ["map()", "print()", "loop()", "repeat()"],
            "answer": "map()",
            "explanation": "The map() method is commonly used to transform arrays into JSX elements."
        },
        {
            "topic": "React Events",
            "question": "Which prop is commonly used to handle a click event in React?",
            "options": ["onClick", "click", "onPressOnly", "handleClickEvent"],
            "answer": "onClick",
            "explanation": "onClick is the standard React event prop for click events."
        },
        {
            "topic": "React Conditional Rendering",
            "question": "Which operator is commonly used for simple conditional rendering?",
            "options": ["Ternary operator", "Modulo operator", "Bitwise operator", "Assignment operator"],
            "answer": "Ternary operator",
            "explanation": "The ternary operator is commonly used for simple conditional rendering."
        },
        {
            "topic": "React Hooks",
            "question": "Where are React Hooks normally used?",
            "options": [
                "Function components",
                "Only CSS files",
                "SQL queries",
                "HTML comments"
            ],
            "answer": "Function components",
            "explanation": "Hooks are primarily used inside React function components."
        }
    ]
}

@app.route("/coding/<language>")
def coding_language(language):

    language = language.lower()

    valid_languages = [
        "python",
        "c",
        "cpp",
        "java",
        "javascript",
        "react"
    ]

    if language not in valid_languages:
        return "Coding language not found", 404

    return render_template(
        "coding_language.html",
        language=language
    )
# ============================================================
# CODING PRACTICE SESSION
# ============================================================

coding_session = {}


def get_coding_questions(language):
    """Return the question list for a coding language."""
    return coding_questions.get(language, [])


def render_coding_question(language, index):
    """Render one coding question."""

    language = language.lower()

    questions = get_coding_questions(language)

    if not questions:
        return "Coding language not found", 404

    # Keep index inside the available range
    if index < 0:
        index = 0

    if index >= len(questions):
        index = len(questions) - 1

    coding_session[language] = index

    question = questions[index]

    return render_template(
        "coding_practice.html",
        section=language.upper(),
        language=language,
        section_key=language,
        question=question,
        question_number=index + 1,
        total_questions=len(questions),
        syllabus_url=url_for(
            "coding_language",
            language=language
        )
    )
# ============================================================
# START CODING PRACTICE
# ============================================================

@app.route("/coding/<language>/practice")
def coding_practice(language):

    language = language.lower()

    if language not in coding_questions:
        return "Coding language not found", 404

    coding_session[language] = 0

    return render_coding_question(language, 0)


# ============================================================
# NEXT CODING QUESTION
# ============================================================

@app.route("/coding/<language>/next")
def coding_next_question(language):

    language = language.lower()

    if language not in coding_questions:
        return "Coding language not found", 404

    current_index = coding_session.get(language, 0)

    # Do NOT restart at question 1
    # Move to the next question
    next_index = current_index + 1

    # Stop at the last available question
    if next_index >= len(coding_questions[language]):
        next_index = len(coding_questions[language]) - 1

    return render_coding_question(language, next_index)


# ============================================================
# PREVIOUS CODING QUESTION
# ============================================================

@app.route("/coding/<language>/previous")
def coding_previous_question(language):

    language = language.lower()

    if language not in coding_questions:
        return "Coding language not found", 404

    current_index = coding_session.get(language, 0)

    previous_index = current_index - 1

    if previous_index < 0:
        previous_index = 0

    return render_coding_question(language, previous_index)

# =========================================================
# TECHNICAL PREPARATION
# =========================================================

@app.route("/technical")
def technical():
    return render_template("technical.html")


# =========================================================
# TECHNICAL BRANCH DATA
# =========================================================

technical_branches = {

    "cse": {
        "name": "CSE",
        "icon": "💻",
        "topics": [
            "Programming",
            "Data Structures",
            "Algorithms",
            "DBMS",
            "Operating Systems",
            "Computer Networks",
            "Object Oriented Programming",
            "Software Engineering",
            "Web Technologies",
            "Computer Architecture"
        ]
    },

    "ise": {
        "name": "ISE",
        "icon": "🖥️",
        "topics": [
            "Programming",
            "Data Structures",
            "Algorithms",
            "DBMS",
            "Operating Systems",
            "Computer Networks",
            "Object Oriented Programming",
            "Software Engineering",
            "Web Technologies",
            "Cloud Computing"
        ]
    },

    "ece": {
        "name": "ECE",
        "icon": "📡",
        "topics": [
            "Electronic Devices",
            "Analog Electronics",
            "Digital Electronics",
            "Network Theory",
            "Signals & Systems",
            "Communication Systems",
            "Microcontrollers",
            "Embedded Systems",
            "VLSI Design",
            "Control Systems",
            "Microwave Engineering",
            "Power Electronics"
        ]
    },

    "eee": {
        "name": "EEE",
        "icon": "⚡",
        "topics": [
            "Electrical Circuits",
            "Electrical Machines",
            "Power Systems",
            "Control Systems",
            "Power Electronics",
            "Electrical Measurements",
            "Digital Electronics",
            "Analog Electronics",
            "Transformers",
            "Renewable Energy"
        ]
    },

    "me": {
        "name": "Mechanical Engineering",
        "icon": "⚙️",
        "topics": [
            "Engineering Mechanics",
            "Thermodynamics",
            "Fluid Mechanics",
            "Heat Transfer",
            "Manufacturing Processes",
            "Machine Design",
            "Strength of Materials",
            "CAD & CAM",
            "IC Engines",
            "Automobile Engineering"
        ]
    },

    "ai-ml": {
        "name": "AI & Machine Learning",
        "icon": "🤖",
        "topics": [
            "Python",
            "Artificial Intelligence",
            "Machine Learning",
            "Deep Learning",
            "Data Science",
            "Statistics",
            "Natural Language Processing",
            "Computer Vision",
            "Neural Networks",
            "Generative AI"
        ]
    },

    "aids": {
        "name": "AI & Data Science",
        "icon": "📊",
        "topics": [
            "Python",
            "Statistics",
            "Data Analytics",
            "Machine Learning",
            "Data Visualization",
            "SQL",
            "Big Data",
            "Deep Learning",
            "Natural Language Processing",
            "Data Mining"
        ]
    },

    "biotech": {
        "name": "Biotechnology",
        "icon": "🧬",
        "topics": [
            "Biochemistry",
            "Cell Biology",
            "Genetics",
            "Microbiology",
            "Molecular Biology",
            "Immunology",
            "Bioinformatics",
            "Genetic Engineering",
            "Bioprocess Engineering",
            "Biotechnology"
        ]
    },

    "aero": {
        "name": "Aerospace Engineering",
        "icon": "✈️",
        "topics": [
            "Aerodynamics",
            "Propulsion",
            "Flight Mechanics",
            "Aircraft Structures",
            "Avionics",
            "Aerospace Materials",
            "Fluid Mechanics",
            "Space Technology",
            "Aircraft Design",
            "Control Systems"
        ]
    }
}


# =========================================================
# COMMON TECHNICAL BRANCH PAGE
# =========================================================

@app.route("/technical/<branch>")
def technical_branch(branch):

    branch = branch.lower()

    if branch not in technical_branches:
        return "Technical branch not found", 404

    data = technical_branches[branch]

    return render_template(
        "technical_branch.html",
        branch=branch,
        branch_name=data["name"],
        branch_icon=data["icon"],
        topics=data["topics"]
    )


# =========================================================
# BRANCH ROUTES
# These are kept because your technical.html uses
# technical_cse, technical_ece, etc.
# =========================================================

@app.route("/technical/cse")
def technical_cse():
    return render_template(
        "technical_branch.html",
        branch="cse",
        branch_name=technical_branches["cse"]["name"],
        branch_icon=technical_branches["cse"]["icon"],
        topics=technical_branches["cse"]["topics"]
    )


@app.route("/technical/ise")
def technical_ise():
    return render_template(
        "technical_branch.html",
        branch="ise",
        branch_name=technical_branches["ise"]["name"],
        branch_icon=technical_branches["ise"]["icon"],
        topics=technical_branches["ise"]["topics"]
    )


@app.route("/technical/ece")
def technical_ece():
    return render_template(
        "technical_branch.html",
        branch="ece",
        branch_name=technical_branches["ece"]["name"],
        branch_icon=technical_branches["ece"]["icon"],
        topics=technical_branches["ece"]["topics"]
    )


@app.route("/technical/eee")
def technical_eee():
    return render_template(
        "technical_branch.html",
        branch="eee",
        branch_name=technical_branches["eee"]["name"],
        branch_name_short="EEE",
        branch_icon=technical_branches["eee"]["icon"],
        topics=technical_branches["eee"]["topics"]
    )


@app.route("/technical/me")
def technical_me():
    return render_template(
        "technical_branch.html",
        branch="me",
        branch_name=technical_branches["me"]["name"],
        branch_icon=technical_branches["me"]["icon"],
        topics=technical_branches["me"]["topics"]
    )


@app.route("/technical/ai-ml")
def technical_ai_ml():
    return render_template(
        "technical_branch.html",
        branch="ai-ml",
        branch_name=technical_branches["ai-ml"]["name"],
        branch_icon=technical_branches["ai-ml"]["icon"],
        topics=technical_branches["ai-ml"]["topics"]
    )


@app.route("/technical/aids")
def technical_aids():
    return render_template(
        "technical_branch.html",
        branch="aids",
        branch_name=technical_branches["aids"]["name"],
        branch_icon=technical_branches["aids"]["icon"],
        topics=technical_branches["aids"]["topics"]
    )


@app.route("/technical/biotech")
def technical_biotech():
    return render_template(
        "technical_branch.html",
        branch="biotech",
        branch_name=technical_branches["biotech"]["name"],
        branch_icon=technical_branches["biotech"]["icon"],
        topics=technical_branches["biotech"]["topics"]
    )


@app.route("/technical/aero")
def technical_aero():
    return render_template(
        "technical_branch.html",
        branch="aero",
        branch_name=technical_branches["aero"]["name"],
        branch_icon=technical_branches["aero"]["icon"],
        topics=technical_branches["aero"]["topics"]
    )


# =========================================================
# TECHNICAL LEARNING PAGE
# =========================================================

@app.route("/technical/<branch>/learn")
def technical_learn(branch):

    branch = branch.lower()

    if branch not in technical_branches:
        return "Technical branch not found", 404

    data = technical_branches[branch]

    return render_template(
        "technical_learn.html",
        branch=branch,
        branch_name=data["name"],
        branch_icon=data["icon"],
        topics=data["topics"]
    )


# =========================================================
# TECHNICAL TOPIC LEARNING CONTENT
# =========================================================

@app.route("/technical/<branch>/learn/<topic>")
def technical_topic(branch, topic):

    branch = branch.lower()

    if branch not in technical_branches:
        return "Technical branch not found", 404

    data = technical_branches[branch]

    topic_name = topic.replace("-", " ").replace("_", " ").title()

    valid_topic = False

    for item in data["topics"]:

        item_url = (
            item.lower()
            .replace("&", "and")
            .replace(" ", "-")
        )

        if item_url == topic.lower():

            valid_topic = True
            topic_name = item
            break

    if not valid_topic:
        return "Technical topic not found", 404

    return render_template(
        "technical_topic.html",
        branch=branch,
        branch_name=data["name"],
        branch_icon=data["icon"],
        topic=topic_name
    )


# =========================================================
# TECHNICAL PRACTICE - AI QUESTION GENERATOR
# =========================================================

def generate_one_technical_question(branch, previous_questions=None):

    import os
    import json
    from groq import Groq

    branch = branch.lower()

    if branch not in technical_branches:
        return None

    data = technical_branches[branch]

    branch_name = data["name"]
    topics = data["topics"]

    if previous_questions is None:
        previous_questions = []

    # -----------------------------------------------------
    # Previous questions
    # -----------------------------------------------------

    previous_text = ""

    if previous_questions:

        previous_text = """
Previous questions already asked:

""" + "\n".join(
            "- " + q for q in previous_questions
        )

        previous_text += """

Do NOT repeat any previous question.
Do NOT create a similar question.
Create a completely different question.
"""

    # -----------------------------------------------------
    # AI PROMPT
    # -----------------------------------------------------

    prompt = f"""
You are an expert technical placement interviewer.

Generate ONE multiple-choice question for:

Branch:
{branch_name}

Important subjects:
{", ".join(topics)}

{previous_text}

Rules:

1. Generate exactly ONE question.
2. The question must be related to {branch_name}.
3. The question must come from one of the subjects.
4. Do not repeat previous questions.
5. Do not make a similar question.
6. Give exactly 4 options.
7. Only one option is correct.
8. Give a short explanation.
9. Make it suitable for engineering placement preparation.
10. Return ONLY valid JSON.

Return exactly:

{{
    "question": "Question text",
    "options": [
        "Option A",
        "Option B",
        "Option C",
        "Option D"
    ],
    "answer": "Option A",
    "explanation": "Explanation"
}}
"""

    # -----------------------------------------------------
    # GROQ API KEY
    # -----------------------------------------------------

    api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:

        print("ERROR: GROQ_API_KEY is missing.")

        return None

    try:

        client = Groq(
            api_key=api_key
        )

        response = client.chat.completions.create(

            model="openai/gpt-oss-120b",

            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert technical "
                        "placement interviewer. "
                        "Return only valid JSON."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],

            temperature=0.8,

            max_completion_tokens=1000,

            response_format={
                "type": "json_object"
            }
        )

        result = (
            response
            .choices[0]
            .message
            .content
            .strip()
        )

        print("\n==============================")
        print("GROQ QUESTION")
        print(result)
        print("==============================\n")

        question_data = json.loads(result)

        question_text = str(
            question_data.get(
                "question",
                ""
            )
        ).strip()

        options = question_data.get(
            "options",
            []
        )

        answer = str(
            question_data.get(
                "answer",
                ""
            )
        ).strip()

        explanation = str(
            question_data.get(
                "explanation",
                ""
            )
        ).strip()

        # -------------------------------------------------
        # Validate
        # -------------------------------------------------

        if not question_text:
            return None

        if not isinstance(options, list):
            return None

        if len(options) != 4:
            return None

        options = [
            str(option).strip()
            for option in options
        ]

        if len(set(options)) != 4:
            return None

        if answer not in options:
            return None

        return {
            "question": question_text,
            "options": options,
            "answer": answer,
            "explanation": explanation
        }

    except Exception as e:

        print("\n==============================")
        print("GROQ QUESTION ERROR")
        print(str(e))
        print("==============================\n")

        return None


# =========================================================
# TECHNICAL PRACTICE PAGE
# =========================================================

@app.route(
    "/technical/<branch>/practice",
    methods=["GET", "POST"]
)
def technical_practice(branch):

    branch = branch.lower()

    if branch not in technical_branches:
        return "Technical branch not found", 404

    data = technical_branches[branch]

    # -----------------------------------------------------
    # Get session data
    # -----------------------------------------------------

    questions = session.get(
        "technical_questions",
        []
    )

    current_index = session.get(
        "technical_current_index",
        0
    )

    answers = session.get(
        "technical_answers",
        {}
    )

    saved_branch = session.get(
        "technical_branch"
    )

    # -----------------------------------------------------
    # Start a fresh session if branch changed
    # -----------------------------------------------------

    if saved_branch != branch:

        questions = []

        current_index = 0

        answers = {}

        session["technical_branch"] = branch

        session["technical_questions"] = []

        session["technical_current_index"] = 0

        session["technical_answers"] = {}

    # -----------------------------------------------------
    # Generate FIRST question
    # -----------------------------------------------------

    if not questions:

        first_question = (
            generate_one_technical_question(
                branch,
                []
            )
        )

        if first_question is None:

            return render_template(
                "technical_practice.html",

                branch=branch,

                branch_name=data["name"],

                branch_icon=data["icon"],

                question=None,

                selected_answer=None,

                feedback=None,

                explanation=None,

                is_correct=None,

                correct_answer=None,

                has_previous=False,

                has_next=False,

                error=(
                    "Unable to generate the question. "
                    "Please try again."
                )
            )

        questions = [first_question]

        current_index = 0

        answers = {}

        session["technical_questions"] = questions

        session["technical_current_index"] = 0

        session["technical_answers"] = {}

    # -----------------------------------------------------
    # Safety check
    # -----------------------------------------------------

    if current_index < 0:
        current_index = 0

    if current_index >= len(questions):
        current_index = len(questions) - 1

    # -----------------------------------------------------
    # Current question
    # -----------------------------------------------------

    question = questions[current_index]

    selected_answer = answers.get(
        str(current_index)
    )

    feedback = None
    explanation = None
    is_correct = None
    correct_answer = None

    # -----------------------------------------------------
    # Answer submitted
    # -----------------------------------------------------

    if request.method == "POST":

        submitted_answer = request.form.get(
            "answer"
        )

        # Only allow answer once
        if (
            submitted_answer
            and selected_answer is None
        ):

            answers[
                str(current_index)
            ] = submitted_answer

            session[
                "technical_answers"
            ] = answers

            selected_answer = submitted_answer

    # -----------------------------------------------------
    # Check answer
    # -----------------------------------------------------

    if selected_answer is not None:

        correct_answer = question["answer"]

        if selected_answer == correct_answer:

            is_correct = True

            feedback = (
                "Excellent! Good answer! 🎉"
            )

        else:

            is_correct = False

            feedback = (
                "Wrong answer! ❌"
            )

        explanation = question.get(
            "explanation",
            ""
        )

    # -----------------------------------------------------
    # Navigation
    # -----------------------------------------------------

    has_previous = (
        current_index > 0
    )

    has_next = (
        selected_answer is not None
    )

    # -----------------------------------------------------
    # Render page
    # -----------------------------------------------------

    return render_template(
        "technical_practice.html",

        branch=branch,

        branch_name=data["name"],

        branch_icon=data["icon"],

        question=question,

        selected_answer=selected_answer,

        feedback=feedback,

        explanation=explanation,

        is_correct=is_correct,

        correct_answer=correct_answer,

        has_previous=has_previous,

        has_next=has_next,

        current_index=current_index,

        error=None
    )

# =========================================================
# TECHNICAL PRACTICE - CHECK ANSWER
# =========================================================

@app.route(
    "/technical/<branch>/practice/answer",
    methods=["POST"]
)
def technical_practice_answer(branch):

    branch = branch.lower()

    if branch not in technical_branches:
        return "Technical branch not found", 404

    questions = session.get(
        "technical_questions",
        []
    )

    current_index = session.get(
        "technical_current_index",
        0
    )

    answers = session.get(
        "technical_answers",
        {}
    )

    # Safety check
    if not questions:
        return redirect(
            url_for(
                "technical_practice",
                branch=branch
            )
        )

    if current_index >= len(questions):
        current_index = len(questions) - 1

    question = questions[current_index]

    # Get selected answer
    selected_answer = request.form.get("answer")

    if not selected_answer:
        return redirect(
            url_for(
                "technical_practice",
                branch=branch
            )
        )

    # Save answer
    answers[str(current_index)] = selected_answer

    session["technical_answers"] = answers

    return redirect(
        url_for(
            "technical_practice",
            branch=branch
        )
    )
# =========================================================
# NEXT QUESTION
# =========================================================

@app.route(
    "/technical/<branch>/practice/next"
)
def technical_practice_next(branch):

    branch = branch.lower()

    if branch not in technical_branches:
        return "Technical branch not found", 404

    questions = session.get(
        "technical_questions",
        []
    )

    current_index = session.get(
        "technical_current_index",
        0
    )

    answers = session.get(
        "technical_answers",
        {}
    )

    # -----------------------------------------------------
    # User must answer first
    # -----------------------------------------------------

    if str(current_index) not in answers:

        return redirect(
            url_for(
                "technical_practice",
                branch=branch
            )
        )

    # -----------------------------------------------------
    # Collect previous questions
    # -----------------------------------------------------

    previous_questions = []

    for q in questions:

        if q.get("question"):

            previous_questions.append(
                q["question"]
            )

    # -----------------------------------------------------
    # Generate NEW question
    # -----------------------------------------------------

    new_question = (
        generate_one_technical_question(
            branch,
            previous_questions
        )
    )

    # -----------------------------------------------------
    # If generation fails
    # -----------------------------------------------------

    if new_question is None:

        return redirect(
            url_for(
                "technical_practice",
                branch=branch
            )
        )

    # -----------------------------------------------------
    # Add question
    # -----------------------------------------------------

    questions.append(
        new_question
    )

    new_index = current_index + 1

    # -----------------------------------------------------
    # Save
    # -----------------------------------------------------

    session["technical_questions"] = questions

    session["technical_current_index"] = new_index

    return redirect(
        url_for(
            "technical_practice",
            branch=branch
        )
    )


# =========================================================
# PREVIOUS QUESTION
# =========================================================

@app.route(
    "/technical/<branch>/practice/previous"
)
def technical_practice_previous(branch):

    branch = branch.lower()

    if branch not in technical_branches:
        return "Technical branch not found", 404

    current_index = session.get(
        "technical_current_index",
        0
    )

    if current_index > 0:

        current_index -= 1

        session[
            "technical_current_index"
        ] = current_index

    return redirect(
        url_for(
            "technical_practice",
            branch=branch
        )
    )


# =========================================================
# RESET PRACTICE
# =========================================================

@app.route(
    "/technical/<branch>/practice/reset"
)
def technical_practice_reset(branch):

    branch = branch.lower()

    if branch not in technical_branches:
        return "Technical branch not found", 404

    session.pop(
        "technical_questions",
        None
    )

    session.pop(
        "technical_current_index",
        None
    )

    session.pop(
        "technical_answers",
        None
    )

    session.pop(
        "technical_branch",
        None
    )

    return redirect(
        url_for(
            "technical_practice",
            branch=branch
        )
    )




# =========================================================
# PROFILE
# =========================================================

@app.route("/profile")
def profile():

    # Check whether user is logged in
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])

    # User no longer exists
    if user is None:
        session.pop("user_id", None)
        return redirect(url_for("login"))

    return render_template(
        "profile.html",
        user=user
    )


# =========================================================
# UPDATE PROFILE
# =========================================================

@app.route("/profile/update", methods=["POST"])
def update_profile():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user = User.query.get(session["user_id"])

    if user is None:
        session.pop("user_id", None)
        session.pop("user", None)

        return redirect(url_for("login"))

    # Basic information
    user.fullname = request.form.get(
        "fullname", ""
    ).strip()

    user.email = request.form.get(
        "email", ""
    ).strip()

    user.phone = request.form.get(
        "phone", ""
    ).strip()

    user.college = request.form.get(
        "college", ""
    ).strip()

    user.branch = request.form.get(
        "branch", ""
    ).strip()

    user.graduation = request.form.get(
        "graduation", ""
    ).strip()

    user.location = request.form.get(
        "location", ""
    ).strip()

    user.about = request.form.get(
        "about", ""
    ).strip()

    # Profile picture
    profile_picture = request.form.get(
        "profile_picture", ""
    ).strip()

    if profile_picture:
        user.profile_picture = profile_picture

    # Update session name too
    session["user"] = user.fullname

    db.session.commit()

    flash(
        "Profile updated successfully!",
        "success"
    )

    return redirect(url_for("profile"))
# RUN FLASK APPLICATION
# =========================================================


if __name__ == "__main__":
    app.run(debug=True)

