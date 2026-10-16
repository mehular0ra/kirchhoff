# Logo sources

Every logo in `assets/logos/` is the owner's official artwork, fetched on 16 Oct 2026 and not edited. The scenes load these local copies; nothing is fetched at render time. All marks are trademarks of their owners and appear only to name the services Kirchhoff runs on or connects to. Each on-screen connector carries a "connector · sandbox" or "simulated" tag. No scene claims a live customer integration.

| File | Mark | Source (official resource or Wikimedia Commons) | Licence and terms |
|---|---|---|---|
| `gmail.svg` | Gmail icon (2020) | https://upload.wikimedia.org/wikipedia/commons/7/7e/Gmail_icon_%282020%29.svg (file page: https://commons.wikimedia.org/wiki/File:Gmail_icon_(2020).svg) | Public domain on Commons; Google trademark |
| `google-drive.svg` | Google Drive icon (2020) | https://upload.wikimedia.org/wikipedia/commons/1/12/Google_Drive_icon_%282020%29.svg (https://commons.wikimedia.org/wiki/File:Google_Drive_icon_(2020).svg) | Public domain on Commons; Google trademark |
| `google-cloud-wordmark-commons.svg` | Google Cloud logo (icon and wordmark), used in S8 | https://upload.wikimedia.org/wikipedia/commons/5/51/Google_Cloud_logo.svg (https://commons.wikimedia.org/wiki/File:Google_Cloud_logo.svg) | Public domain on Commons; Google trademark |
| `google-cloud.svg` | Google Cloud wordmark (full colour), kept as an alternative | https://www.gstatic.com/cgc/google-cloud-logo-fullcolor.svg (linked from https://cloud.google.com/icons) | Google brand asset; Google trademark |
| `gemini-icon.svg` | Gemini spark icon (2025) | https://upload.wikimedia.org/wikipedia/commons/1/1d/Google_Gemini_icon_2025.svg (https://commons.wikimedia.org/wiki/File:Google_Gemini_icon_2025.svg) | Public domain on Commons; Google trademark |
| `gemini-wordmark.svg` | Gemini wordmark, kept as an alternative | https://upload.wikimedia.org/wikipedia/commons/8/8a/Google_Gemini_logo.svg (https://commons.wikimedia.org/wiki/File:Google_Gemini_logo.svg) | Public domain on Commons; Google trademark |
| `vertex-ai.svg` | Vertex AI product icon | Google Cloud official icon pack: https://services.google.com/fh/files/misc/core-products-icons.zip → `Unique Icons/Vertex AI/SVG/VertexAI-512-color.svg` (pack linked from https://cloud.google.com/icons) | Google Cloud icon terms on https://cloud.google.com/icons; Google trademark |
| `cloud-run.svg` | Cloud Run product icon | Same pack → `Unique Icons/Cloud Run/SVG/CloudRun-512-color-rgb.svg` | As above |
| `firebase-icon.svg` | Firebase logomark (full colour) | Firebase brand assets: https://firebase.google.com/static/downloads/brand-guidelines/firebase-brand-assets.zip → `Firebase Logo/Primary Logomark/SVG/Logomark_Full Color.svg` (from https://firebase.google.com/brand-guidelines) | Firebase brand guidelines; Google trademark |
| `firebase-lockup.svg` | Firebase horizontal lockup, kept as an alternative | Same zip → `Firebase Logo/Primary Lockup/SVG/Primary_Horizontal_Lockup_Full_Color.svg` | As above |
| `firestore.svg` | Cloud Firestore product logomark | Same zip → `Firebase Product Icons/Product Logomark/SVG/Product_Logomark_Cloud_Firestore_Full_Color.svg` | As above |
| `sap.svg` | SAP logo (2011) | https://upload.wikimedia.org/wikipedia/commons/5/59/SAP_2011_logo.svg (https://commons.wikimedia.org/wiki/File:SAP_2011_logo.svg) | Public domain on Commons; SAP SE trademark |

Wikimedia licence fields were read from the Commons API (`extmetadata.LicenseShortName` = "Public domain", `Restrictions` = "trademarked") on 16 Oct 2026.

**Brand rules followed:** logos are shown in full colour at their own proportions, on white, with clear space. They are not recoloured, cropped or combined into new marks. The Kirchhoff mark is the team's own (`apps/web/public/kirchhoff.svg`, inlined in `lib/stage.js`).

**Fonts** (in `assets/fonts/`, both SIL Open Font License 1.1, licence files alongside): Inter variable with the opsz axis (`@fontsource-variable/inter` 5.3.0) and JetBrains Mono variable (`@fontsource-variable/jetbrains-mono` 5.3.0), both copied from `apps/web/node_modules`.
