"""Write the fixed fixtures every Week 7 measurement runs against.

    python fixtures/make_fixtures.py

triage_messages.json  40 unique messages (the course's Thursday Lab 1 list)
traffic_100.json      100 calls: each unique message once + 60 seeded repeats, shuffled
backlog_24.json       24 after-hours SMS messages for the batch queue (lever 2)

Synthetic teaching data. No real patients.
"""
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEED = 7

TOPICS = [
    'Fever for two days, drinking fluids', 'Persistent cough for a week',
    'Child with diarrhoea since morning', 'Mild headache after missing lunch',
    'Chest pain radiating to left arm', 'Twisted ankle, mild swelling',
    'Rash spreading on the forearm', 'Sore throat, no fever',
    'Shortness of breath climbing stairs', 'Stomach pain after eating',
    'Toothache for three days', 'Low-grade fever with body aches',
    'Cut on hand, bleeding stopped', 'Dizziness on standing up quickly',
    'Ear pain and mild hearing loss', 'Back pain after lifting a jerry can',
    'Blurred vision since this morning', 'Swollen ankle, cannot bear weight',
    'Persistent vomiting since last night', 'Mild burn on the forearm',
    'High fever with stiff neck', 'Sudden weakness on one side',
    'Difficulty breathing after a bee sting', 'Severe abdominal pain, rigid',
    'Coughing up blood', 'Chest tightness at rest',
    'Mild seasonal allergy symptoms', 'Sprained wrist from a fall',
    'Sore muscles after exercise', 'Common cold symptoms, no fever',
    'Insect bite with local swelling', 'Minor scrape on the knee',
    'Heartburn after a heavy meal', 'Feeling tired, no other symptoms',
    'Nosebleed that stopped on its own', 'Sunburn on shoulders',
    'Mild anxiety before an exam', 'Hiccups lasting one hour',
    'Bruise on the shin from a bump', 'Runny nose and sneezing',
]


def main() -> None:
    assert len(set(TOPICS)) == 40
    rng = random.Random(SEED)
    calls = list(TOPICS) + [rng.choice(TOPICS) for _ in range(60)]
    rng.shuffle(calls)

    backlog = rng.sample(TOPICS, 24)

    (HERE / "triage_messages.json").write_text(json.dumps(TOPICS, indent=2) + "\n")
    (HERE / "traffic_100.json").write_text(json.dumps(calls, indent=2) + "\n")
    (HERE / "backlog_24.json").write_text(json.dumps(backlog, indent=2) + "\n")
    print(f"wrote triage_messages.json (40), traffic_100.json ({len(calls)}, "
          f"{len(set(calls))} unique), backlog_24.json ({len(backlog)})")


if __name__ == "__main__":
    main()
