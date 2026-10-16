"""Seed reference data for the Pharmacy Management environment."""

# (patient_id, name, date_of_birth, email, phone, medical_history)
PATIENTS = [
    ("PAT001", "Alice Green", "1985-04-12", "alice.green@mail.com", "555-2001", "Hypertension, Type 2 Diabetes"),
    ("PAT002", "Bob Nguyen",  "1990-08-25", "bob.nguyen@mail.com",  "555-2002", "Asthma"),
    ("PAT003", "Carol Kim",   "1978-11-30", "carol.kim@mail.com",   "555-2003", "Hyperthyroidism"),
    ("PAT004", "David Patel", "2000-01-15", "david.patel@mail.com", "555-2004", "No significant history"),
    ("PAT005", "Eva Rossi",   "1965-07-22", "eva.rossi@mail.com",   "555-2005", "High cholesterol, Osteoporosis"),
    ("PAT006", "Frank Osei",  "1995-03-08", "frank.osei@mail.com",  "555-2006", "Seasonal allergies"),
    ("PAT007", "Grace Liu",   "1982-09-17", "grace.liu@mail.com",   "555-2007", "Depression, Anxiety"),
    ("PAT008", "Hector Cruz", "1970-12-05", "hector.cruz@mail.com", "555-2008", "COPD"),
    ("PAT009", "Iris Walsh",  "1988-06-28", "iris.walsh@mail.com",  "555-2009", "Migraine"),
    ("PAT010", "Jake Sato",   "2005-02-14", "jake.sato@mail.com",   "555-2010", "Eczema"),
]

# (physician_id, name, license_number, email, affiliated_clinic, specialty)
PHYSICIANS = [
    ("PHY001", "Dr. Samantha Reed",   "MD-SR-1001", "s.reed@cityclinic.com",   "City Medical Center",    "Internal Medicine"),
    ("PHY002", "Dr. Marcus Chen",     "MD-MC-1002", "m.chen@heartcare.com",    "Heart & Vascular Care",  "Cardiology"),
    ("PHY003", "Dr. Priya Sharma",    "MD-PS-1003", "p.sharma@wellnesspro.com","Wellness Pro Clinic",    "Family Medicine"),
    ("PHY004", "Dr. James O'Brien",   "MD-JO-1004", "j.obrien@neuromed.com",   "NeuroMed Institute",     "Neurology"),
    ("PHY005", "Dr. Leila Ahmadi",    "MD-LA-1005", "l.ahmadi@pulmonary.com",  "Pulmonary Care Center",  "Pulmonology"),
    ("PHY006", "Dr. Carlos Mendez",   "MD-CM-1006", "c.mendez@endocrine.com",  "Endocrine Specialists",  "Endocrinology"),
    ("PHY007", "Dr. Nadia Kovacs",    "MD-NK-1007", "n.kovacs@mindhealth.com", "Mind Health Clinic",     "Psychiatry"),
    ("PHY008", "Dr. Thomas Wright",   "MD-TW-1008", "t.wright@allergy.com",    "Allergy & Immunology",   "Allergy"),
]

# (medication_id, name, form, strength, manufacturer, classification, storage_requirements)
MEDICATIONS = [
    ("MED001", "Metformin",     "tablet",    "500mg",       "PharmaCo",     "prescription", "Room temperature"),
    ("MED002", "Atorvastatin",  "tablet",    "20mg",        "MedSupply Inc","prescription", "Room temperature"),
    ("MED003", "Lisinopril",    "tablet",    "10mg",        "HealthGen",    "prescription", "Room temperature"),
    ("MED004", "Albuterol",     "injection", "2.5mg/3ml",   "BioPharm",     "prescription", "Room temperature, away from heat"),
    ("MED005", "Levothyroxine", "tablet",    "50mcg",       "ThyroMed",     "prescription", "Room temperature"),
    ("MED006", "Sertraline",    "tablet",    "50mg",        "MindPharm",    "prescription", "Room temperature"),
    ("MED007", "Amoxicillin",   "capsule",   "500mg",       "AntiBio Corp", "prescription", "Room temperature"),
    ("MED008", "Ibuprofen",     "tablet",    "400mg",       "GenericMeds",  "OTC",          "Room temperature"),
    ("MED009", "Cetirizine",    "tablet",    "10mg",        "AllergyPlus",  "OTC",          "Room temperature"),
    ("MED010", "Fluticasone",   "topical",   "0.05%",       "DermaCare",    "prescription", "Room temperature"),
    ("MED011", "Oxycodone",     "tablet",    "5mg",         "PainControl",  "controlled",   "Secure storage, room temperature"),
    ("MED012", "Omeprazole",    "capsule",   "20mg",        "GastroMed",    "OTC",          "Room temperature"),
    ("MED013", "Sumatriptan",   "tablet",    "50mg",        "MigraineRx",   "prescription", "Room temperature"),
    ("MED014", "Prednisone",    "tablet",    "10mg",        "ImmunoPharm",  "prescription", "Room temperature"),
    ("MED015", "Hydrochlorothiazide", "tablet", "25mg",     "CardioMeds",   "prescription", "Room temperature"),
]
