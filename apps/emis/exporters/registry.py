from .uganda import UgandaExporter
from .kenya import KenyaExporter
from .rwanda import RwandaExporter
from .tanzania import TanzaniaExporter

EXPORTERS = {
    "uganda_moes": UgandaExporter,
    "kenya_moe": KenyaExporter,
    "rwanda_reb": RwandaExporter,
    "tanzania_moevt": TanzaniaExporter,
}


def get_exporter(country_template):
    try:
        return EXPORTERS[country_template]()
    except KeyError:
        raise ValueError(
            f"No exporter registered for '{country_template}'. "
            f"Available: {', '.join(EXPORTERS)}"
        )
