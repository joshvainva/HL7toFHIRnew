"""
Mapping layer — routes a ParsedHL7Message to the correct converter
and returns a FHIR Bundle.
"""
from typing import Any, Dict, List, Tuple

from app.core.parser import ParsedHL7Message
from app.converters.base import build_bundle
from app.converters.adt import ADTConverter
from app.converters.oru import ORUConverter
from app.converters.orm import ORMConverter
from app.converters.siu import SIUConverter
from app.converters.mdm import MDMConverter
from app.converters.dft import DFTConverter
from app.converters.vxu import VXUConverter
from app.converters.mfn import MFNConverter
from app.converters.ack import ACKConverter
from app.converters.bar import BARConverter
from app.converters.generic import GenericConverter


# Registry: message_type → converter class
CONVERTER_REGISTRY: Dict[str, Any] = {
    "ADT": ADTConverter,
    "ORU": ORUConverter,
    "ORM": ORMConverter,
    "SIU": SIUConverter,
    "MDM": MDMConverter,
    "DFT": DFTConverter,
    "VXU": VXUConverter,
    "MFN": MFNConverter,
    "ACK": ACKConverter,
    "BAR": BARConverter,
}


class FHIRMapper:
    """
    Selects and invokes the appropriate HL7 → FHIR converter,
    then wraps results in a FHIR Bundle.
    """

    def map(self, parsed_msg: ParsedHL7Message) -> Tuple[Dict[str, Any], List[str], List[Any]]:
        """
        Convert parsed HL7 message to FHIR Bundle.

        Returns:
            (fhir_bundle_dict, list_of_warnings, list_of_field_mappings)
        """
        msg_type = parsed_msg.message_type.upper()
        converter_class = CONVERTER_REGISTRY.get(msg_type, GenericConverter)
        converter = converter_class()

        resources, warnings, field_mappings = converter.convert(parsed_msg)
        bundle = build_bundle(resources, bundle_type="collection")

        return bundle, warnings, field_mappings
