progress bar und cli --> eins nutzt click library das andere was anderes --> warum? I guess that during the new implementation we didnt sticked properly to the already established conventions.
Overall i see this with the progress bars the most.
We had one in an earlier version that was green, slick and looked overall better, more compact also graphically. I would like that we have this overall, maybe decouple the graphic / ui rendering from the other logic at this point? This should be checked, if its better code-wise to seperate the logic here from the presentation. So we can change it at one place later - and not chase it over the whole code base.

maybe related
There is still this old ugly white bar UI in the terminal for the progress bars. We had previously a green, slick progress bar, i think this came with the click implementation, but i am not entirely sure.
I want one unified UI for this.

And we need more control over the amount of stuff displayed in the terminal, i want to be able to filter out more now, show less information while still keeping the ability to view it this detailed.

---

message-id , referal id etc.. should be also fetched and written in the frontmatter.
Then we can construct real markdown links (maybe in a second pass) to actually link these files 

Same with send emails (not only received ones)

I want that the links in the markdown notes completely represent the relationships of the mails - both send and received ones. This way its easy to visualize the pathing of a conversation in Obsidian (through local graphs for example)

---

OAuth Imap Access (tohuwabohu.halle@outlook.de)
The question is how hard it is to implement this, specially the "register your app with microsoft" part.

I think this is more important than i care to admit. I have atleast one important email adress thats over oAuth, and this has to be checked regularly. Excluding it from the system makes no sense.

---

I thought about the categorisation issue. Right now its pretty basic. 
First should be a better prompting (like i have for the meetings) to output a consistent, Obsidian Task compatible task format. Then in Obsidian build a Task query that filters and shows tasks from mails.

---

Another idea expanding on this. I want atleast a start for a categorisation based on our projects.
I am thinking how this could work effectively.
All projects are stored in a very strict folder system, with a strict naming convention. There is always a certain named markdown files with metadata, links and basic information about the project (wich also acts as main point for dealing with projects) - this makes it easy to parse all projects (with possible filters, so i can just process projects after a certain date that are self-financed and managed by NICA)

This way we can get a structured representation of all this (either just in a json, xml, yaml or whatever suitable format - this has to be carefully checked about the pros and cons)

So its easy for example to identify a certain modifier for this project like "2026_NICA_DSEE_Titel" wich also gives us info about the year, wich society, wich founding program, wich project title"

Also it gives date information (when does it started or ends) and linked email-adresses.

Then we can use a similar idea of the white-list (or basically just expanding on the whitelist) - and say for example: for a certain email adress in a certain date range - i link this email (in the metadata, by setting a property) also to a certain project.

I didnt thought it entirely through - this needs some critical analysis and certainly a red-teaming.

But i see this as a possible easy expandable aproach.