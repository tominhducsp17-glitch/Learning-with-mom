Custom fonts for DOCX/MathType rendering.

This directory is mounted into the Docker container at runtime. Put local font
files here when Word equations need Windows/MathType fonts such as:

- MTEXTRA.TTF
- symbol.ttf
- times.ttf, timesbd.ttf, timesi.ttf, timesbi.ttf
- cour.ttf, courbd.ttf, couri.ttf, courbi.ttf

Do not commit the font files. They are ignored by git.
