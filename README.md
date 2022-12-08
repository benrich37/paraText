<img src="https://www.colorado.edu/cs/profiles/express/themes/ucb/images/cu-boulder-logo-text-black.svg" alt="CU Boulder Logo" width="500">

# Software Engineering for Scientists <br/> paraText Project

## Introduction
The objective of this project is to write an application that expands contextual information of advanced vocabulary found in technical texts. The user right clicks on an underlined word for replacement options. The user would then shift and click to toggle sync options for the highlighted word. When the text is red, this indicates that all instances of that word has been replaced with the same options. If the text is in yellow, this indicates that the change for the text is unique and will not trigger changes in other instances of the word. 

The motivation of this project is based on the need to make technical writing more accessible to a general audience. Communication of an educated audience requires specific vernacular native to that field. This is different for an uneducated audience where communication requires additional context. Our goal for this project is to create an expandable text interpretation tool for increasing accessibility to scientific texts. We have designed a Python GUI as the prototype for future HCI projects that aim to create interactive texts that provide contextual meaning for any targetted audience. 

## Current Problem 
As science continues to grow rapidly with new fields and knowledge, so does the complexity of the vocabulary. For the uneducated audience, too much time is spent on re-reading text and using outside resources to patch together a contextualized understanding. The result is that the learning experience is fragmented and often co-dependent on several resources. paraText attempts to eliminate this through the use of an interactive text that gives replacement options for confusing phrases and words outside of everyday vernacular.

<p align="center">
   <img src="https://user-images.githubusercontent.com/91628000/206314640-c4285ff6-91e2-4e8c-b529-abb598c202ca.png" width=75% height=75%>
</p>



## Application 
This is a screen recording showing how it works. The words highlighted in red are synced, meaning that if one of them is changed, all instances of that word will be changed. If it’s yellow, only one instance of the word will be changed, not both. 

https://user-images.githubusercontent.com/91628000/206312726-d8b5bc65-f743-4a87-8cc3-4c8e8ae6e28d.mov

## Running the Program
To run this program, go to the folder demos and select the file demos.py. Ensure that the `__file__` is set to paraText.py. An example is below:

<p align="center">
   <img src="https://user-images.githubusercontent.com/91628000/206366906-09739e57-7d19-4d7a-9756-3173e3a538bb.png" width=75% height=75%>
</p>

From the base terminal type in python demos.py. A GUI will pop up. 
  

  


