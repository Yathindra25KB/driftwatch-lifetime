"""Registry of the upstream datasets: where they live, what they contain, how to cite them.

Facts here were read from the publishers' pages on 10 Oct 2026; anything not confirmed
there is tagged [verify] and listed in the data cards (docs/data_cards/).
"""

from __future__ import annotations

from dataclasses import dataclass

CACHE_VERSION = "v1"


@dataclass(frozen=True)
class LamdaSource:
    repo_id: str = "IQSeC-Lab/LAMDA"
    repo_type: str = "dataset"
    subset: str = "Baseline"
    # Only the Baseline subset, its feature mapping, the root metadata file and the card.
    allow_patterns: tuple[str, ...] = ("Baseline/*", "metadata.csv", "README.md")
    # 2015 has no folder upstream (README: "2013 to 2025 (excluding 2015)").
    years: tuple[int, ...] = (2013, 2014, *range(2016, 2026))
    splits: tuple[str, ...] = ("train", "test")
    n_features: int = 4561
    feature_prefix: str = "feat_"
    meta_columns: tuple[str, ...] = ("hash", "label", "family", "vt_count", "year_month")
    licence: str = "MIT"
    url: str = "https://huggingface.co/datasets/IQSeC-Lab/LAMDA"
    citation: str = (
        "Haque, M. A., Hossain, I., Kamol, M. M., Alam, M. J., Amalapuram, S. K., "
        "Talukder, S., & Rahman, M. S. (2026). LAMDA: A Longitudinal Android Malware "
        "Benchmark for Concept Drift Analysis. ICLR 2026. arXiv:2505.18551."
    )


@dataclass(frozen=True)
class BodmasSource:
    drive_folder_id: str = "1Uf-LebLWyi9eCv97iBal7kL1NgiGEsv_"
    files: tuple[str, ...] = ("bodmas.npz", "bodmas_metadata.csv", "bodmas_malware_category.csv")
    features_file: str = "bodmas.npz"
    metadata_file: str = "bodmas_metadata.csv"
    n_features: int = 2381
    # Licence: the BODMAS page states none; the build guide says BSD-2-Clause [verify].
    licence: str = "BSD-2-Clause [verify]"
    url: str = "https://whyisyoung.github.io/BODMAS/"
    citation: str = (
        "Yang, L., Ciptadi, A., Laziuk, I., Ahmadzadeh, A., & Wang, G. (2021). BODMAS: "
        "An Open Dataset for Learning based Temporal Analysis of PE Malware. "
        "4th Deep Learning and Security Workshop (DLS)."
    )

    @property
    def folder_url(self) -> str:
        return f"https://drive.google.com/drive/folders/{self.drive_folder_id}"


LAMDA = LamdaSource()
BODMAS = BodmasSource()
DATASETS = ("lamda", "bodmas")
