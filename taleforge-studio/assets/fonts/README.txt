Bundled fonts (SIL Open Font License 1.1 — see OFL-Andika.txt / OFL-Amiri.txt)

  Andika-Regular.ttf / Andika-Bold.ttf
      SIL Andika — designed for literacy learners: unambiguous a/g/l/I,
      generous x-height. Default Latin face for picture books.

  Amiri-Regular.ttf / Amiri-Bold.ttf
      Amiri — classical Naskh Arabic, fully shaped and kerned.

The render service registers them automatically (app/services/fonts.py) and
picks the right face per script:
  * Latin              -> Andika
  * Arabic / RTL text  -> Amiri (+ arabic-reshaper & python-bidi when installed)

To use a different face, drop the TTF here and add it to CANDIDATES in
app/services/fonts.py, or point FONT_DIR at another folder.

Fallback order if a font is missing: DejaVu -> Noto -> Helvetica (Latin only).
