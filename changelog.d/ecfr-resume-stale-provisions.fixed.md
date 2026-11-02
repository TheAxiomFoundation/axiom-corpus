Run the eCFR cached-source check in every extraction mode. Before this, a resume could store a replacement XML snapshot beside provisions parsed from the old bytes. A title has cached provisions but no stored snapshot matching its inventory pin. If such a title fails, or a graphic-transcription run will not commit it because another title failed, the run now raises before writing any source, image, inventory, provision or coverage file:

- Fetched runs keep this behaviour, which they already had.
- Section-filtered and graphic-transcription runs gain it.
- `--source-xml` runs gain it too. A run no longer writes the local XML into the store at the start; it stages that XML with the other source writes, which happen only after every title passes validation.

A title with no cached provisions still records a graphic failure as a resumable title error and keeps its new snapshot for the resume.
