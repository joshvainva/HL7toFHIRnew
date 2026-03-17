"""
Basic integration tests for the HL7 → FHIR conversion pipeline.

Run with:  pytest tests/ -v
"""
import pytest
from app.core.parser import HL7Parser, HL7ParseError
from app.core.validator import HL7Validator
from app.core.mapper import FHIRMapper


ADT_MSG = (
    "MSH|^~\\&|SND|FAC|RCV|DEST|20240101120000||ADT^A01|MSG001|P|2.5\r"
    "EVN|A01|20240101120000\r"
    "PID|1||MRN001^^^HOSP^MR||DOE^JOHN^A||19800315|M\r"
    "PV1|1|I|ICU^101^A|E|||NPI123^SMITH^JANE|||SUR\r"
)

ORU_MSG = (
    "MSH|^~\\&|LAB|LABFAC|RCV|DEST|20240101130000||ORU^R01|MSG002|P|2.5\r"
    "PID|1||MRN002^^^HOSP^MR||JONES^MARY||19901010|F\r"
    "OBR|1|ORD001|FILL001|718-7^Hemoglobin^LN|||20240101125000\r"
    "OBX|1|NM|718-7^Hemoglobin^LN||13.5|g/dL|12.0-16.0|N|||F\r"
)

ORM_MSG = (
    "MSH|^~\\&|OE|HOSP|LAB|LABFAC|20240101140000||ORM^O01|MSG003|P|2.5\r"
    "PID|1||MRN003^^^HOSP^MR||SMITH^ALICE||19751225|F\r"
    "ORC|NW|ORD002||GRP001|||||20240101140000|||NPI456^BROWN^BOB\r"
    "OBR|1|ORD002||85025^CBC^LN\r"
)


parser = HL7Parser()
validator = HL7Validator()
mapper = FHIRMapper()


# ─────────────────────────── Parser tests ──────────────────────────────────

class TestParser:
    def test_adt_parse(self):
        msg = parser.parse(ADT_MSG)
        assert msg.message_type == "ADT"
        assert msg.message_event == "A01"
        assert msg.version == "2.5"

    def test_oru_parse(self):
        msg = parser.parse(ORU_MSG)
        assert msg.message_type == "ORU"
        assert msg.message_event == "R01"

    def test_orm_parse(self):
        msg = parser.parse(ORM_MSG)
        assert msg.message_type == "ORM"

    def test_empty_raises(self):
        with pytest.raises(HL7ParseError):
            parser.parse("")

    def test_no_msh_raises(self):
        with pytest.raises(HL7ParseError):
            parser.parse("PID|1||MRN001\r")

    def test_normalizes_newlines(self):
        # Should handle \n as well as \r
        msg_lf = ADT_MSG.replace("\r", "\n")
        result = parser.parse(msg_lf)
        assert result.message_type == "ADT"


# ─────────────────────────── Validator tests ───────────────────────────────

class TestValidator:
    def test_valid_adt(self):
        msg = parser.parse(ADT_MSG)
        result = validator.validate(msg)
        assert result.valid is True
        assert len(result.errors) == 0

    def test_valid_oru(self):
        msg = parser.parse(ORU_MSG)
        result = validator.validate(msg)
        assert result.valid is True


# ─────────────────────────── Mapper / Converter tests ──────────────────────

class TestMapper:
    def test_adt_produces_bundle(self):
        msg = parser.parse(ADT_MSG)
        bundle, warnings = mapper.map(msg)
        assert bundle["resourceType"] == "Bundle"
        assert len(bundle["entry"]) >= 1

    def test_adt_contains_patient(self):
        msg = parser.parse(ADT_MSG)
        bundle, _ = mapper.map(msg)
        types = [e["resource"]["resourceType"] for e in bundle["entry"]]
        assert "Patient" in types

    def test_adt_contains_encounter(self):
        msg = parser.parse(ADT_MSG)
        bundle, _ = mapper.map(msg)
        types = [e["resource"]["resourceType"] for e in bundle["entry"]]
        assert "Encounter" in types

    def test_oru_contains_observation(self):
        msg = parser.parse(ORU_MSG)
        bundle, _ = mapper.map(msg)
        types = [e["resource"]["resourceType"] for e in bundle["entry"]]
        assert "Observation" in types
        assert "DiagnosticReport" in types

    def test_orm_contains_service_request(self):
        msg = parser.parse(ORM_MSG)
        bundle, _ = mapper.map(msg)
        types = [e["resource"]["resourceType"] for e in bundle["entry"]]
        assert "ServiceRequest" in types

    def test_patient_name_extracted(self):
        msg = parser.parse(ADT_MSG)
        bundle, _ = mapper.map(msg)
        patient = next(
            e["resource"] for e in bundle["entry"]
            if e["resource"]["resourceType"] == "Patient"
        )
        assert patient.get("name") is not None
        assert patient["name"][0].get("family", "").upper() == "DOE"

    def test_observation_value(self):
        msg = parser.parse(ORU_MSG)
        bundle, _ = mapper.map(msg)
        obs = next(
            e["resource"] for e in bundle["entry"]
            if e["resource"]["resourceType"] == "Observation"
        )
        assert "valueQuantity" in obs
        assert obs["valueQuantity"]["value"] == 13.5


# ─────────────────────────── Renderer tests ────────────────────────────────

class TestRenderer:
    def test_json_output(self):
        import json
        from app.core.renderer import to_fhir_json
        msg = parser.parse(ADT_MSG)
        bundle, _ = mapper.map(msg)
        json_str = to_fhir_json(bundle)
        parsed = json.loads(json_str)
        assert parsed["resourceType"] == "Bundle"

    def test_xml_output(self):
        from app.core.renderer import to_fhir_xml
        msg = parser.parse(ADT_MSG)
        bundle, _ = mapper.map(msg)
        xml_str = to_fhir_xml(bundle)
        assert "<Bundle" in xml_str

    def test_human_readable(self):
        from app.core.renderer import to_human_readable
        msg = parser.parse(ADT_MSG)
        bundle, warnings = mapper.map(msg)
        report = to_human_readable(bundle, msg.version, msg.message_type, msg.message_event, warnings)
        assert "FHIR" in report
        assert "Patient" in report
