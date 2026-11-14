"""Step 4: Explore available SBB Open Data catalog datasets.

This lists dataset METADATA, NOT actual ZVV pass prices. It is an investigation
of the professor's suggested source, not an implemented fare-price API.
"""
import requests

URL = "https://data.sbb.ch/api/explore/v2.1/catalog/datasets"


def main():
    for search_term in ("tarif", "preis", "ticket"):
        print(f"\nSBB open datasets matching '{search_term}':")
        try:
            response = requests.get(
                URL, params={"search": search_term, "limit": 8}, timeout=30
            )
            response.raise_for_status()
            datasets = response.json().get("results", [])
        except (requests.RequestException, ValueError) as error:
            print("Catalog lookup failed:", error)
            continue
        if not datasets:
            print("No matching datasets returned.")
        for dataset in datasets:
            dataset_id = dataset.get("dataset_id", "unknown")
            title = dataset.get("metas", {}).get("default", {}).get("title", "")
            print(f"- {dataset_id}: {title}")
    print("\nRead https://data.sbb.ch/api-console/explore/v2.1/ for the API documentation.")
    print("Important: this search does not verify subscription pricing availability.")


if __name__ == "__main__":
    main()
