[1mdiff --git a/setup.py b/setup.py[m
[1mindex 1ec089d..368d1c9 100644[m
[1m--- a/setup.py[m
[1m+++ b/setup.py[m
[36m@@ -8,8 +8,7 @@[m [msetup([m
     long_description_content_type="text/markdown",[m
     author="Ergonaut Community",[m
     url="https://github.com/ergonaut-airdrop/token-flight",[m
[31m-    package_dir={"": "."},[m
[31m-    packages=find_packages(where=".") + ["src"],[m
[32m+[m[32m    packages=["src"],[m
     package_data={[m
         "": ["*.json", "*.env*"],[m
         "src": ["art/*", "ui/*"][m
