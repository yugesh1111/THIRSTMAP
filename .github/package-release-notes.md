The ThirstMap pipeline as a pip package: the generator, the validity checks, the scorer, the evaluation harness and
every pipeline stage as one `thirstmap` command. Built and tested by GitHub Actions from this tag.

```bash
pip install https://github.com/yugesh1111/THIRSTMAP/releases/download/v1.0.0/thirstmap-1.0.0-py3-none-any.whl
thirstmap generate --level 3 --seed 11 --twin --out my_scenes     # one scene + its twin, checked
thirstmap list                                                     # every stage as a subcommand
```

Extras: `[real]` for real terrain (rasterio), `[models]` for model adapters, `[docs]` for the summary PDF.
Try it without installing anything: the Colab notebook `ThirstMap_quickstart.ipynb` in the repository.
The dataset itself is in the `dataset-v1.0` release.
