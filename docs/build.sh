#!/bin/bash

rm -Rf build/*

rm -Rf /tmp/agt-docs-src/
cp -Rf ../src /tmp/agt-docs-src/
cp -f ../README.md /tmp/agt-docs-src/

cp -R _static/* source/_static/
find /tmp/agt-docs-src/ -name *.md | xargs sed -i 's/\.\.\/\.\.\/\.\.\/docs\///g'

sed -i 's/\.\/docs\///g' /tmp/agt-docs-src/README.md

sed -i -r 's/\(src\/examples\/([^\/]*)\//(\1.html/g' /tmp/agt-docs-src/README.md

sphinx-build -b html source build

rm -Rf build/.doctrees/
find build -name *html | xargs sed -i 's/\.\.\/\.\.\/\.\.\/README.md/overview.html/g'

rm -Rf /tmp/agt-docs-src/

