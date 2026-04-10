"""
This script demonstrates how to process Synthea FHIR bundles to create
training data for fhir-synth. It performs two main steps:

1.  **Extract Key Info**: It reads FHIR bundles (one per patient), parses them,
    and extracts the most clinically relevant information into a simplified
    text summary. This summary is easier for an LLM to process than raw FHIR.

2.  **Generate Prompt**: It uses a powerful LLM (e.g., GPT-4o) to convert
    the text summary into a high-level, natural-language prompt suitable
    for use with fhir-synth.

This `(prompt, original_fhir_json)` pair can then be used as a training
example to optimize the fhir-synth pipeline with DSPy.

Setup:
1.  Install required libraries:
    pip install 'fhir.resources>=7.1.0' openai

2.  Download and unzip Synthea data into a directory (e.g., `synthea_data/`).
    You can get sample data from:
    https://github.com/synthetichealth/synthea-sample-data/tree/main/downloads

3.  Set your OpenAI API key in your environment:
    export OPENAI_API_KEY="your_api_key_here"

Usage:
    python examples/create_training_prompts.py /path/to/synthea_data_dir
"""
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from openai import OpenAI


def calculate_age(birth_date_str: str) -> int:
    """Calculate age from a birthDate string."""
    birth_date = datetime.strptime(birth_date_str, "%Y-%m-%d")
    return (datetime.now() - birth_date).days // 365


def extract_key_info_from_bundle(bundle: dict) -> dict | None:
    """
    Parses a raw FHIR Bundle dict to extract a simplified summary of a patient's record.
    """
    patient = None
    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        if resource.get("resourceType") == "Patient":
            patient = resource
            break
    if not patient:
        return None

    patient_info: dict = {
        "gender": patient.get("gender", "unknown"),
        "age": calculate_age(patient.get("birthDate", "1970-01-01")),
        "conditions": [],
        "medications": [],
        "procedures": [],
        "key_observations": [],
        "care_plans": [],
        "document_references": [],
        "immunizations": [],
        "allergy_intolerances": [],
        "medication_dispenses": [],
        "encounters": [],
        "medications_list": [],
        "care_teams": [],
        "diagnostic_reports": [],
        "goals": [],
        "locations": [],
        "organizations": [],
        "practitioners": [],
        "practitioner_roles": [],
        "provenances": [],
        "service_requests": [],
        "persons": [],
        "related_persons": [],
    }

    def _text(obj: dict | None) -> str:
        return (obj or {}).get("text", "") if isinstance(obj, dict) else ""

    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        rtype = resource.get("resourceType", "")
        if rtype == "Condition":
            t = _text(resource.get("code"))
            if t:
                patient_info["conditions"].append(t)
        elif rtype == "MedicationRequest":
            t = _text(resource.get("medicationCodeableConcept"))
            if t:
                patient_info["medications"].append(t)
        elif rtype == "Procedure":
            t = _text(resource.get("code"))
            if t:
                patient_info["procedures"].append(t)
        elif rtype == "Observation" and resource.get("valueQuantity"):
            code_text = _text(resource.get("code"))
            if "Body Mass Index" in code_text or "Blood pressure" in code_text:
                vq = resource["valueQuantity"]
                patient_info["key_observations"].append(
                    f"{code_text}: {vq.get('value')} {vq.get('unit', '')}"
                )
        elif rtype == "CarePlan":
            cats = resource.get("category") or []
            if cats:
                t = _text(cats[0])
                if t:
                    patient_info["care_plans"].append(t)
        elif rtype == "DocumentReference":
            t = _text(resource.get("type"))
            if t:
                patient_info["document_references"].append(t)
        elif rtype == "Immunization":
            t = _text(resource.get("vaccineCode"))
            if t:
                patient_info["immunizations"].append(t)
        elif rtype == "AllergyIntolerance":
            t = _text(resource.get("code"))
            if t:
                patient_info["allergy_intolerances"].append(t)
        elif rtype == "MedicationDispense":
            t = _text(resource.get("medicationCodeableConcept"))
            if t:
                patient_info["medication_dispenses"].append(t)
        elif rtype == "Encounter":
            types = resource.get("type") or []
            if types:
                t = _text(types[0])
                if t:
                    patient_info["encounters"].append(t)
        elif rtype == "Medication":
            t = _text(resource.get("code"))
            if t:
                patient_info["medications_list"].append(t)
        elif rtype == "CareTeam":
            cats = resource.get("category") or []
            if cats:
                t = _text(cats[0])
                if t:
                    patient_info["care_teams"].append(t)
        elif rtype == "DiagnosticReport":
            t = _text(resource.get("code"))
            if t:
                patient_info["diagnostic_reports"].append(t)
        elif rtype == "Goal":
            t = _text(resource.get("description"))
            if t:
                patient_info["goals"].append(t)
        elif rtype == "Location":
            t = resource.get("name", "")
            if t:
                patient_info["locations"].append(t)
        elif rtype == "Organization":
            t = resource.get("name", "")
            if t:
                patient_info["organizations"].append(t)
        elif rtype == "Practitioner":
            names = resource.get("name") or []
            if names:
                t = names[0].get("text", "")
                if t:
                    patient_info["practitioners"].append(t)
        elif rtype == "PractitionerRole":
            codes = resource.get("code") or []
            if codes:
                t = _text(codes[0])
                if t:
                    patient_info["practitioner_roles"].append(t)
        elif rtype == "Provenance":
            agents = resource.get("agent") or []
            if agents:
                display = (agents[0].get("who") or {}).get("display", "")
                if display:
                    patient_info["provenances"].append(display)
        elif rtype == "ServiceRequest":
            t = _text(resource.get("code"))
            if t:
                patient_info["service_requests"].append(t)
        elif rtype == "Person":
            names = resource.get("name") or []
            if names:
                t = names[0].get("text", "")
                if t:
                    patient_info["persons"].append(t)
        elif rtype == "RelatedPerson":
            names = resource.get("name") or []
            if names:
                t = names[0].get("text", "")
                if t:
                    patient_info["related_persons"].append(t)

    # Deduplicate lists
    list_keys = [
        "conditions", "medications", "procedures", "care_plans", "document_references",
        "immunizations", "allergy_intolerances", "medication_dispenses", "encounters",
        "medications_list", "care_teams", "diagnostic_reports", "goals", "locations",
        "organizations", "practitioners", "practitioner_roles", "provenances",
        "service_requests", "persons", "related_persons",
    ]
    for key in list_keys:
        patient_info[key] = sorted(set(patient_info[key]))

    return patient_info


def generate_prompt_from_summary(summary: dict, client: OpenAI) -> str:
    """
    Uses an LLM to generate a high-level prompt from the patient summary.
    """
    summary_text = f"""
    - Gender: {summary['gender']}
    - Age: {summary['age']}
    - Conditions: {', '.join(summary['conditions'])}
    - Medications: {', '.join(summary['medications'])}
    - Procedures: {', '.join(summary['procedures'])}
    - Key Observations: {', '.join(summary['key_observations'])}
    - Care Plans: {', '.join(summary['care_plans'])}
    - Document References: {', '.join(summary['document_references'])}
    - Immunizations: {', '.join(summary['immunizations'])}
    - Allergies: {', '.join(summary['allergy_intolerances'])}
    - Medication Dispenses: {', '.join(summary['medication_dispenses'])}
    - Encounters: {', '.join(summary['encounters'])}
    - Medications List: {', '.join(summary['medications_list'])}
    - Care Teams: {', '.join(summary['care_teams'])}
    - Diagnostic Reports: {', '.join(summary['diagnostic_reports'])}
    - Goals: {', '.join(summary['goals'])}
    - Locations: {', '.join(summary['locations'])}
    - Organizations: {', '.join(summary['organizations'])}
    - Practitioners: {', '.join(summary['practitioners'])}
    - Practitioner Roles: {', '.join(summary['practitioner_roles'])}
    - Provenances: {', '.join(summary['provenances'])}
    - Service Requests: {', '.join(summary['service_requests'])}
    - Persons: {', '.join(summary['persons'])}
    - Related Persons: {', '.join(summary['related_persons'])}
    """

    system_prompt = (
        "You are an expert clinical summarizer. Your task is to convert a "
        "structured list of clinical facts about a patient into a high-level, "
        "natural-language paragraph. This paragraph will be used as a prompt "
        "to a synthetic data generator, so it should capture the essence of the "
        "patient's story without getting lost in minor details. Focus on the "
        "primary diagnoses and the overall clinical picture."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"Please summarize the following patient data into a single paragraph prompt:\n{summary_text}",
                },
            ],
            temperature=0.5,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        return ""


def main():
    """
    Main function to process a directory of Synthea FHIR bundles.
    """
    if len(sys.argv) < 2:
        print("Usage: python examples/create_training_prompts.py /path/to/synthea_fhir_dir")
        sys.exit(1)

    synthea_dir = Path(sys.argv[1])
    if not synthea_dir.is_dir():
        print(f"Error: Directory not found at {synthea_dir}")
        sys.exit(1)

    output_dir = Path("runs/training_examples")
    output_dir.mkdir(exist_ok=True, parents=True)

    client = OpenAI()

    all_files = sorted(synthea_dir.glob("*.json"))
    print(f"Found {len(all_files)} patient bundles in {synthea_dir}")
    file_count = 0
    skipped = 0
    for fhir_file in all_files:
        example_name = fhir_file.stem
        prompt_file = output_dir / f"{example_name}_prompt.txt"
        data_file = output_dir / f"{example_name}_data.json"

        # Skip already-processed files so re-runs don't incur extra API cost
        if prompt_file.exists() and data_file.exists():
            skipped += 1
            continue

        print(f"Processing {fhir_file.name}...")
        with open(fhir_file, "r") as f:
            bundle_json = json.load(f)

        summary = extract_key_info_from_bundle(bundle_json)
        if not summary:
            continue

        prompt = generate_prompt_from_summary(summary, client)
        if not prompt:
            continue

        with open(prompt_file, "w") as f:
            f.write(prompt)
        with open(data_file, "w") as f:
            json.dump(bundle_json, f, indent=2)

        print(f"  -> Saved prompt to {prompt_file}")
        file_count += 1

    print(f"\nDone: {file_count} new pairs generated, {skipped} already existed.")

if __name__ == "__main__":
    main()

