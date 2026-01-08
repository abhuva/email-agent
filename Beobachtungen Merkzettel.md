"from" wird oft so geliefert: "ImmoScout24" <meinkonto@immobilienscout24.de>
this breaks yaml frontmatter.

A solution - there seems to be always the mail-adress part AND a naming part. Check if this is possible to seperate.

---
Dates sometimes get written like this: "Wed, 13 Sep 2023 14:34:53 +0200 (CEST)" instead of this: "2023-10-16T11:59:10Z" - check if its possible to enforce (and why is it even happening? thats the big question, the data is not from an LLM, its from the mail - so it should be consistent, or?)