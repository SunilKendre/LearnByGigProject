gigs_list = [
    {
        'id': 1,
        'high_level_desc': 'Build a flask  app that accept data(name,college,branch,language known,project etc) from a user (no need of user  creation) and stores that data. Each CV should be readable on http://localhost:5000/cv/1./cv/2...so on',
        'steps': {
            1: 'Build bare mininum flask app with hello world without using any html template or render template',
            2: 'Make a list of fields you want to fetch from the user fro creating his/her CV',
            3: 'Create a route "/dummy" and show dummy hardcoded date for  one simple user with the above listed atrributes ',
            4: 'Create database with one table and colums as mentioned in #2',
            5: 'Create a route "/createcv" with fields and text fields as mentioned in #2 and stored data in database once saved.keep styling simple bootstrap.',
            6: 'Create a route "/cv/1" and the FIRST cv should be readable on this page .Use simple html/bootstrap elements .No need of hi-fi  design.',

        }
    },
    {
        'id': 2,
        'high_level_desc': 'Write a simple telegram bot with /start command',
        'steps': {
            1: 'Build bare mininum telegram app with python-telegram-bot package with one command /start  with commandhandler',
        }
        'instructions':{
            1:'Submit video over unlisted Youtube or drive'
        }
    },
    {
        'id': 3,
        'high_level_desc': 'Design a website using html and css',
        'steps': {
            1: 'Plan your layout.The First step of any website is always to know what you want on it and how you want it to look',
            2: 'Create the elements in your layout',
            3: 'Fill in the HTML content',
            4: 'Add some basic layout CSS',
            5: 'Add more specific styles',
            6: 'Add Colors and background',

        }
]
