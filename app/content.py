"""Event copy lives here so it can be edited without touching logic.
Items dynamically pull defaults or environment settings."""
from .config import settings

EVENT_NAME = settings.EVENT_NAME
TAGLINE = settings.TAGLINE
ORGANISER = settings.ORGANISER
VENUE = settings.VENUE

ABOUT = [
    f"Bring your team of two to five students ({settings.MIN_TEAM_MEMBERS} to {settings.MAX_TEAM_MEMBERS} members) and solve a real-world problem that matters to people. "
    "You submit your idea and presentation first, then build a prototype during the 24-hour hackathon.",
    "There is a single round. Every update, instruction and announcement goes to your "
    "Team Leader's mobile number and email, so make sure both are correct when you register.",
]

TRACKS = [
    "Human Safety, Rights & Empowerment",
    "Health, Education & Digital Innovation",
    "Sustainability, Smart Communities & Social Entrepreneurship",
    "AI in Hospitality and Management",
]

FAQ = [
    ("Who can form a team?",
     f"A team has {settings.MIN_TEAM_MEMBERS} to {settings.MAX_TEAM_MEMBERS} members including the Team Leader. All members should currently be college students (undergraduate or postgraduate)."),
    ("What does it cost?",
     f"The registration fee is ₹{settings.REGISTRATION_FEE_PER_MEMBER_INR} per student / participant (e.g., ₹{settings.REGISTRATION_FEE_PER_MEMBER_INR * 2} for 2 members, ₹{settings.REGISTRATION_FEE_PER_MEMBER_INR * 3} for 3 members, ₹{settings.REGISTRATION_FEE_PER_MEMBER_INR * 4} for 4 members, or ₹{settings.REGISTRATION_FEE_PER_MEMBER_INR * 5} for 5 members), paid securely online through Razorpay."),
    ("What do we submit while registering?",
     "An idea title (max 100 chars), an abstract (max 10,000 chars), a detailed description (max 50,000 chars), and an idea presentation (.pptx or .ppt presentation deck, up to 10 MB). Download our standard presentation template right from this page."),
    ("Is there more than one round?",
     "No. The hackathon has a single round with direct prototype evaluation."),
    ("Where is the hackathon held?",
     f"The hackathon is hosted at {settings.VENUE}."),
    ("How will we receive updates?",
     "Official instructions, keys, track updates and announcements are sent to the Team Leader's mobile number and email."),
    ("What if our payment fails?",
     "Your registration details are securely kept with pending status. You can retry the payment anytime without re-entering data."),
    ("Can we get a refund?",
     "Refund conditions are governed by the Organiser's Terms & Conditions. Once processed and team slot confirmed, fees are generally non-refundable except in case of event cancellation."),
]

# ---------- Terms & Conditions (Section 6) ----------
TERMS_VERSION = "v1"

TERMS_CHECKBOX_LABEL = (
    "I confirm that I am authorised to register on behalf of my team and that all team members have "
    "read and agree to the Terms & Conditions. I understand and agree that JM Vertex Technologies may "
    "use, adapt and build upon the ideas, presentations and prototypes submitted through this "
    "registration for its research and development purposes."
)

TERMS_POINTS = [
    {
        "title": "Originality & Intellectual Property",
        "desc": "Teams confirm the submitted idea is their own original work and does not infringe upon any third-party intellectual property or copyright."
    },
    {
        "title": "R&D and Usage Rights",
        "desc": "Teams grant JM Vertex Technologies the right to use, adapt and build upon submitted ideas, presentations and prototypes for its research and development purposes."
    },
    {
        "title": "Data Privacy & Communication",
        "desc": "Team contact details are strictly used only for official communications regarding the hackathon, logistical arrangements, and schedule updates."
    },
    {
        "title": "Registration Fee & Refunds",
        "desc": f"The registration fee is ₹{settings.REGISTRATION_FEE_PER_MEMBER_INR} per member. Fees are non-refundable once registration is confirmed, except under cancellation by the organisers."
    },
    {
        "title": "Schedule & Rule Amendments",
        "desc": "Organisers reserve the right to amend the event schedule or challenge rules by informing the Team Leader's registered email address and mobile number."
    }
]
