# Crossword stats

Download and display your NYTimes Crossword statistics.

## Setup

Install dependencies:

    pip3 install requests numpy matplotlib


To get your user ID and login cookie,
open https://www.nytimes.com/crosswords in a browser and login to your account.
Open the developer console (ctrl-shift-i on Chrome)
and paste the following snippet:

```
console.log(JSON.stringify({
  'user_id': decodeURI(document.querySelector("a[href^='mailto:nytgames@nytimes.com']").href).match(/Regi%3A (\d+)/)[1],
  'cookie': document.cookie.match(/NYT-S=([^;]+)/i)[1]
}));
```

Copy the resulting data to a file in this directory named `user_info.json`.
Check the `user_info.example.json` file to see what this should look like.

NOTE: This user data will allow the Python script to read your puzzles,
so be sure not to post the contents of this file publically as it enables
others to access your account without needing your password.

