it seems during run its first fetching all mails (with no progress bar) and processing them - with progress bar. intented behaviour would be that also during the fetching stage there is a progress bar.

---

It would be nice to have an estimated time left. This could be done simply by doing:

100 * current time running /  percentage done 

Atleast if my logic is right here.


# next version

- lots of mail has their info in html stuff - how do we handle this right now? is it possible to use these (maybe just directly sending to the llm - in case we currently only sending a sanitized version)

- whitelist blacklist is important now, as this would drastically change the final scoring (most likely we take the score from the llm and change it based on whitelist / blacklist)

- sqlite is now a serious consideration, we can get more and more data - in order to analyse it, it would most likely be super slow in markdown to process. This needs to be researched, but in the end, if we wanna do data analysis - we need other tools most likely.
  BUT - and this is important: The markdown stays how it is, its the source of truth for the vault.
  Additional analysis with a database or similar, this would be done aside / ontop of the markdown files.

- seperate mail accounts needs to be implemented now. This is mainly a question how to structure the config.yaml (and some code changes) - the core logic of fetching/processing isnt touched i think.
  I want to be able to define multiple accounts in the config. 
  Have an additional command for the runtime to either go through all of them - or a specific one.
  It has to be considered if an even more complex setup (different config files per mail account) is worth it, what it mean in the future (how hard is it to do later compared to now) - so that each mail account could in theory be processed with different prompts/white-blacklists etc. - a custom setup for each account.
  This would mean handling way more files for the setup - many of them wich are the same.
  One idea would be a "mod" aproach - often mods in games use this modding thing, where you can write a file in a "mirrored" folder, like instead of /scripts/  its writing in /mods/scripts   -> and basically everything in the mod folder overwrites what is happening at runtime, but the fallback is always the /scripts/  --> obviously this is metaphor in a way.
  For us this would mean having a default setup of files (configs, prompts etc.) and a folder/file structure similar to the mod idea - but here we have the "account names" from the mail accounts we target (or aliases, wich might be easier for a folder name)
  And if we process this account, we take the setup from this folder (and all missing ones from the default.)
  
  This could mean first setting the defaults anyway, then checking into the folder and atleast for configs, only set what is in the file (means i could only change 1-2 properties, instead of having to mirror the whole file) - 
  
  I defintly want to discuss this in detail - this kind of extensability could prove fantastic later.