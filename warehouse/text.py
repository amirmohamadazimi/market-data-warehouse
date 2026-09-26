_FA = str.maketrans({
        "ك": "ک",
        "ي": "ی",
        "ى": "ی",
    })

def normalize_fa(s):
    """Replace Arabic letters that TSE uses with their Persian forms.

    Leaves None and non-Persian text (e.g. 'SPY') unchanged.
    """
    if s is None:
        return None

    return s.translate(_FA)
