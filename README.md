# CEMCLRN-Final-Project
To run tier 1:
---

Download credentials.txt from the group chat. This allows the program to send files to the GDrive folder without authenticating the user.

Place the file in the same folder as disaster_scrape.py. Then in command prompt, install the needed python libraries, then type the command:

`python disaster_scrape.py`

Open the google drive folder from the output link generated or use [this link](https://drive.google.com/drive/folders/1CK-3noRfwvlntTZyidVAOQgJ26pbAlnn)

To access the folder in google colab, open the folder and click "add shortcut to drive". Then, run this code in a cell:

```py
from google.colab import drive
drive.mount('/content/drive')
disasterscsv = pd.read_csv("/content/drive/MyDrive/DisasterArticles/disaster_articless.csv")
```
