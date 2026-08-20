from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


# =========================================================
# USER
# =========================================================

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    fullname = db.Column(
        db.String(100),
        nullable=False
    )

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )

    college = db.Column(
        db.String(150),
        nullable=False
    )

    branch = db.Column(
        db.String(100),
        nullable=False
    )

    password = db.Column(
        db.String(200),
        nullable=False
    )

    phone = db.Column(
    db.String(20),
    nullable=True
   )

    location = db.Column(
    db.String(100),
    nullable=True
   )

    graduation_year = db.Column(
    db.String(10),
    nullable=True
    )

    career_goal = db.Column(
    db.String(150),
    nullable=True
    )

    about = db.Column(
    db.Text,
    nullable=True
    )

    skills = db.Column(
    db.Text,
    nullable=True
    )

    profile_picture = db.Column(
    db.String(255),
    nullable=True
    )

    # =====================================================
    # NOTIFICATION PREFERENCES
    # =====================================================

    ai_interview_notifications = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    daily_practice_notifications = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    weekly_progress_notifications = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    def __repr__(self):
        return f"<User {self.fullname}>"


# =========================================================
# COMPANY
# =========================================================

class Company(db.Model):
    __tablename__ = "companies"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    industry = db.Column(
        db.String(100)
    )

    description = db.Column(
        db.Text
    )

    hiring_process = db.Column(
        db.Text
    )

    def __repr__(self):
        return f"<Company {self.name}>"


# =========================================================
# INTERVIEW QUESTION
# =========================================================

class InterviewQuestion(db.Model):
    __tablename__ = "interview_question"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    company = db.Column(
        db.String(100)
    )

    year = db.Column(
        db.String(10)
    )

    category = db.Column(
        db.String(50)
    )

    question = db.Column(
        db.Text
    )

    def __repr__(self):
        return f"<InterviewQuestion {self.id}>"


# =========================================================
# USED INTERVIEW QUESTION
# =========================================================

class UsedInterviewQuestion(db.Model):
    __tablename__ = "used_interview_questions"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    question_id = db.Column(
        db.Integer,
        db.ForeignKey("interview_question.id"),
        nullable=False
    )

    round_type = db.Column(
        db.String(50),
        nullable=False
    )

    def __repr__(self):
        return (
            f"<UsedInterviewQuestion "
            f"user={self.user_id} "
            f"question={self.question_id}>"
        )


# =========================================================
# AI INTERVIEW QUESTION
# =========================================================

class AIInterviewQuestion(db.Model):
    __tablename__ = "ai_interview_questions"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    question_code = db.Column(
        db.String(20),
        unique=True,
        nullable=False
    )

    round_type = db.Column(
        db.String(50),
        nullable=False
    )

    question = db.Column(
        db.Text,
        nullable=False
    )

    option_a = db.Column(
        db.String(300)
    )

    option_b = db.Column(
        db.String(300)
    )

    option_c = db.Column(
        db.String(300)
    )

    option_d = db.Column(
        db.String(300)
    )

    correct_answer = db.Column(
        db.String(1)
    )

    def __repr__(self):
        return f"<AIInterviewQuestion {self.question_code}>"


# =========================================================
# USER PRACTICE PROGRESS
# =========================================================

class PracticeProgress(db.Model):
    __tablename__ = "practice_progress"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    practice_type = db.Column(
        db.String(50),
        nullable=False
    )

    completed = db.Column(
        db.Integer,
        default=0,
        nullable=False
    )

    total = db.Column(
        db.Integer,
        default=0,
        nullable=False
    )

    @property
    def percentage(self):
        if self.total == 0:
            return 0

        return round(
            (self.completed / self.total) * 100
        )

    def __repr__(self):
        return (
            f"<PracticeProgress "
            f"user={self.user_id} "
            f"type={self.practice_type}>"
        )
