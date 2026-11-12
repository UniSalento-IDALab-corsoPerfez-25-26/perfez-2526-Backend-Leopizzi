"""Fonti del dataset aria. Per aggiungerne una: sottoclasse di
api.aria.fonti.base.FonteAria in questo package, poi aggiungerla qui."""

from api.aria.fonti.arpa import FonteARPA
from api.aria.fonti.cams import FonteCAMS
from api.aria.fonti.eea import FonteEEA
from api.aria.fonti.openaq import FonteOpenAQ


def fonti_aria():
    """Istanze di tutte le fonti del dataset aria, nell'ordine in cui
    compaiono nel dataset."""
    return [FonteARPA(), FonteOpenAQ(), FonteEEA(), FonteCAMS()]
