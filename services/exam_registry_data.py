"""
Canonical exam registry.

This is a SEED list of well-known Rajasthan exams (it exists to give the
normalizer/matcher something to match against, and to give discovery a
starting name+authority pair). It is explicitly NOT a claim that these
are the only supported exams — services/exam_discovery.py can register
new Exam entries at runtime when a user searches for something not in
this list and it can be found on an allowlisted authority site.
"""

EXAM_REGISTRY = [
    {"id": "cet_senior_secondary", "name": "CET Senior Secondary Level",
     "aliases": ["cet 12", "cet 12th", "cet senior secondary", "cet sr secondary"],
     "authority_id": "rssb", "category": "CET", "levels": ["Senior Secondary"]},

    {"id": "cet_graduation", "name": "CET Graduation Level",
     "aliases": ["cet graduation", "cet grad", "cet graduate"],
     "authority_id": "rssb", "category": "CET", "levels": ["Graduation"]},

    {"id": "patwar", "name": "Patwari / Patwar",
     "aliases": ["patwar", "patwari"], "authority_id": "rsmssb",
     "category": "Subordinate Service", "levels": []},

    {"id": "vdo", "name": "Village Development Officer (VDO)",
     "aliases": ["vdo", "village development officer"], "authority_id": "rsmssb",
     "category": "Subordinate Service", "levels": []},

    {"id": "ldc", "name": "Lower Division Clerk (LDC)",
     "aliases": ["ldc", "lower division clerk"], "authority_id": "rsmssb",
     "category": "Clerical", "levels": []},

    {"id": "junior_assistant", "name": "Junior Assistant",
     "aliases": ["junior assistant", "jr assistant"], "authority_id": "rsmssb",
     "category": "Clerical", "levels": []},

    {"id": "lab_assistant", "name": "Lab Assistant",
     "aliases": ["lab assistant", "laboratory assistant"], "authority_id": "rssb",
     "category": "Technical", "levels": ["Science", "Geography", "General"]},

    {"id": "agriculture_supervisor", "name": "Agriculture Supervisor",
     "aliases": ["agriculture supervisor", "agri supervisor"],
     "authority_id": "rsmssb", "category": "Technical", "levels": []},

    {"id": "animal_attendant", "name": "Animal Attendant",
     "aliases": ["animal attendant", "pashu parichar"], "authority_id": "rsmssb",
     "category": "Technical", "levels": []},

    {"id": "junior_instructor", "name": "Junior Instructor",
     "aliases": ["junior instructor", "jr instructor"], "authority_id": "rssb",
     "category": "Technical", "levels": []},

    {"id": "police_si", "name": "Sub Inspector (Police SI)",
     "aliases": ["si", "sub inspector", "police si", "rajasthan si"],
     "authority_id": "rpsc", "category": "Police", "levels": []},

    {"id": "ras", "name": "Rajasthan Administrative Service (RAS)",
     "aliases": ["ras", "rajasthan administrative service"],
     "authority_id": "rpsc", "category": "Gazetted", "levels": []},

    {"id": "school_lecturer", "name": "School Lecturer (1st Grade Teacher)",
     "aliases": ["1st grade", "first grade", "school lecturer", "lecturer",
                 "1st grade teacher"], "authority_id": "rpsc",
     "category": "Teaching", "levels": ["1st Grade"]},

    {"id": "senior_teacher", "name": "Senior Teacher (2nd Grade Teacher)",
     "aliases": ["2nd grade", "second grade", "senior teacher",
                 "2nd grade teacher", "upper primary teacher"],
     "authority_id": "rssb", "category": "Teaching", "levels": ["2nd Grade"]},

    {"id": "primary_teacher_l1", "name": "Primary Teacher Level-1 (3rd Grade Teacher)",
     "aliases": ["3rd grade", "third grade", "3rd grade teacher",
                 "primary teacher", "primary teacher level 1",
                 "primary school teacher"], "authority_id": "rssb",
     "category": "Teaching", "levels": ["Level 1"]},

    {"id": "reet_level_1", "name": "REET Level 1",
     "aliases": ["reet level 1", "reet l1", "reet lvl 1"],
     "authority_id": "rajeduboard", "category": "Teacher Eligibility",
     "levels": ["Level 1"]},

    {"id": "reet_level_2", "name": "REET Level 2",
     "aliases": ["reet level 2", "reet l2", "reet lvl 2"],
     "authority_id": "rajeduboard", "category": "Teacher Eligibility",
     "levels": ["Level 2"]},

    {"id": "rajasthan_high_court", "name": "Rajasthan High Court Recruitment",
     "aliases": ["high court", "rajasthan high court", "hcraj"],
     "authority_id": "hcraj", "category": "Judiciary Staff", "levels": []},
]

EXAM_REGISTRY_BY_ID = {exam["id"]: exam for exam in EXAM_REGISTRY}
