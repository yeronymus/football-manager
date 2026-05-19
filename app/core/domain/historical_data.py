# app/core/domain/historical_data.py

# Game results for Games 1-7 (Historical/Legacy)
GAMES_1_7 = [
    {
        "id": 1, "date": "2026-01-17", "score": "13:7:4", 
        "W": ["Dias Bekbosyn", "Vlad Lishanlo", "Aldiyar Kazbekov", "Miras Mukanov", "Said Soltanzade", "Yernur Bauyrzhanuly"],
        "L": ["Arsen Kudaibergen", "Aidyn Galymbekov", "Umid Kamilov", "Daryn Bakyrkhan", "Zhanibek Xenbek", "Aktan Abdullaatov", "Alikhan Muratuly", "Yeldos Ismailov", "Assylbek Nurmagambetov", "Ansar Tanirbay", "Bakhtiyar Temirbayev", "Raimbek Sarzhakov"],
        "goals": {"Dias Bekbosyn": 5, "Vlad Lishanlo": 3, "Aldiyar Kazbekov": 2, "Miras Mukanov": 2, "Said Soltanzade": 1, "Yernur Bauyrzhanuly": 1, "Arsen Kudaibergen": 3, "Aidyn Galymbekov": 2, "Umid Kamilov": 1, "Zhanibek Xenbek": 1, "Yeldos Ismailov": 2, "Bakhtiyar Temirbayev": 1, "Raimbek Sarzhakov": 1},
        "mvp": ["Dias Bekbosyn"]
    },
    {
        "id": 2, "date": "2026-01-24", "score": "13:12", 
        "W": ["Nurkabyl Sharipbay", "Said Soltanzade", "Mirlan Toktoshev", "Daryn Bakyrkhan", "Yernur Bauyrzhanuly", "Aktan Abdullaatov", "Zhanibek Xenbek", "Dastan Sadyraliyev", "Assylbek Nurmagambetov"],
        "L": ["Vlad Lishanlo", "Iliyas Akbergen", "Arsen Kudaibergen", "Aidyn Galymbekov", "Yeldos Ismailov", "Yerik Yekibay", "Dias Bekbosyn", "Yermakhan Borankhan", "Adil Baizhanov"],
        "goals": {"Nurkabyl Sharipbay": 7, "Said Soltanzade": 1, "Mirlan Toktoshev": 2, "Vlad Lishanlo": 3, "Iliyas Akbergen": 2, "Arsen Kudaibergen": 2, "Aidyn Galymbekov": 2},
        "mvp": ["Nurkabyl Sharipbay"]
    },
    {
        "id": 3, "date": "2026-01-31", "score": "8:11", 
        "W": ["Beka", "Daulet Bekmolda", "Asset Khassan", "Yermakhan Borankhan", "Dias Bekbosyn", "Iliyas Akbergen", "Zhanibek Xenbek", "Viktor Snytkin", "Alikhan Muratuly"],
        "L": ["Dastan Sadyraliyev", "Daryn Bakyrkhan", "Vlad Lishanlo", "Aidyn Galymbekov", "Said Soltanzade", "Yerik Yekibay", "Assylbek Nurmagambetov", "Mansur Mutayev", "Raimbek Sarzhakov"],
        "goals": {"Asset Khassan": 1, "Iliyas Akbergen": 6, "Viktor Snytkin": 1, "Daryn Bakyrkhan": 1, "Vlad Lishanlo": 3, "Aidyn Galymbekov": 1, "Mansur Mutayev": 1, "Raimbek Sarzhakov": 1},
        "mvp": ["Iliyas Akbergen"]
    },
    {
        "id": 4, "date": "2026-02-08", "score": "10:5", 
        "W": ["Zhanibek Xenbek", "Vlad Lishanlo", "Daryn Bakyrkhan", "Bakhtiyar Temirbayev", "Yernar Bestikpayev", "Said Soltanzade", "Dias August", "Dastan Sadyraliyev", "Aidyn Galymbekov", "Raimbek Sarzhakov"],
        "L": ["Adok Salimzhan", "Akhmetov Dias", "Mansur Mutayev", "Medeu Yersain", "Yerik Yekibay", "Yermakhan Borankhan", "Mirlan Toktoshev", "Daulet Bekmolda", "Viktor Snytkin", "Aktan Abdullaatov"],
        "goals": {"Zhanibek Xenbek": 1, "Vlad Lishanlo": 4, "Bakhtiyar Temirbayev": 2, "Said Soltanzade": 1, "Dias August": 2, "Mansur Mutayev": 4, "Mirlan Toktoshev": 1},
        "mvp": ["Zhanibek Xenbek", "Adok Salimzhan"]
    },
    {
        "id": 5, "date": "2026-02-14", "score": "10:13", 
        "W": ["Iosif Vassilenko", "Akhmetov Dias", "Asset Khassan", "Dias Bekbosyn", "Said Soltanzade", "Yerik Yekibay", "Dias Kaibar", "Viktor Snytkin", "Vlad Lishanlo", "Assylbek Nurmagambetov"],
        "L": ["Dastan Sadyraliyev", "Daulet Bekmolda", "Yermakhan Borankhan", "Niyaz Bayankulov", "Aldiyar Kazbekov", "Mirlan Toktoshev", "Daryn Bakyrkhan", "Aidyn Galymbekov", "Raimbek Sarzhakov", "Miras Mukanov"],
        "goals": {"Said Soltanzade": 1, "Dias Kaibar": 4, "Viktor Snytkin": 4, "Vlad Lishanlo": 2, "Assylbek Nurmagambetov": 2, "Aldiyar Kazbekov": 2, "Daryn Bakyrkhan": 1, "Aidyn Galymbekov": 2, "Raimbek Sarzhakov": 1, "Miras Mukanov": 3},
        "mvp": ["Dias Kaibar", "Miras Mukanov"]
    },
    {
        "id": 6, "date": "2026-02-21", "score": "5:5", 
        "W": [], "L": [], 
        "D": ["Nurkabyl Sharipbay", "Miras Mukanov", "Iliyas Akbergen", "Adok Salimzhan", "Dias Bekbosyn", "Mukhammed A Askar", "Niyaz Bayankulov", "Yermakhan Borankhan", "Aidyn Kassym", "Alikhan Muratuly", "Dias Kaibar", "Daryn Bakyrkhan", "Vlad Lishanlo", "Ansar Tanirbay", "Aldiyar Kazbekov", "Mirlan Toktoshev", "Asset Khassan", "Almas Kaneshev", "Yernar Bestikpayev", "Aktan Abdullaatov"],
        "goals": {"Nurkabyl Sharipbay": 4, "Miras Mukanov": 1, "Vlad Lishanlo": 1},
        "mvp": [] 
    },
    {
        "id": 7, "date": "2026-02-28", "score": "6:3", 
        "W": ["Dastan Sadyraliyev", "Yernur Bauyrzhanuly", "Daryn Bakyrkhan", "Yernar Bestikpayev", "Nurken Samigullin", "Dias Bekbosyn", "Aidyn Galymbekov", "Iliyas Akbergen", "Miras Mukanov", "Nurkabyl Sharipbay", "Mirlan Toktoshev"],
        "L": ["Aidyn Kassym", "Zhanibek Xenbek", "Niyaz Bayankulov", "Asset Khassan", "Aldiyar Kazbekov", "Yeldos Ismailov", "Adok Salimzhan", "Bakhtiyar Temirbayev", "Umid Kamilov", "Vlad Lishanlo"],
        "goals": {"Nurkabyl Sharipbay": 3, "Miras Mukanov": 1, "Mirlan Toktoshev": 1, "Adok Salimzhan": 1, "Vlad Lishanlo": 1, "Aldiyar Kazbekov": 1},
        "mvp": []
    }
]

PLAYER_PROPS = {
    "Dias Bekbosyn": {"pos": "CAM", "alt": "CM, FWD, CDM, LW, RW"},
    "Yermakhan Borankhan": {"pos": "RB", "alt": ""},
    "Medeu Yersain": {"pos": "CB", "alt": "RB"},
    "Yerik Yekibay": {"pos": "CDM", "alt": "LW"},
    "Ansar Tanirbay": {"pos": "CDM", "alt": ""},
    "Daryn Bakyrkhan": {"pos": "CM", "alt": "CB, LB, RW"},
    "Miras Mukanov": {"pos": "RW", "alt": "LW, CM, FWD"},
    "Bakhtiyar Temirbayev": {"pos": "RB", "alt": "RM, RW, LW"},
    "Akhmetov Dias": {"pos": "RB", "alt": "RM"},
    "Mukhammed A Askar": {"pos": "FWD", "alt": "LB, CDM, CM"},
    "Viktor Snytkin": {"pos": "FWD", "alt": "FWD"},
    "Aldiyar Kazbekov": {"pos": "CAM", "alt": "CM, CDM"},
    "Iliyas Akbergen": {"pos": "CM", "alt": "LM, RM, RW, LW"},
    "Adil Baizhanov": {"pos": "CB", "alt": "LB, RB, RW, LW"},
    "Vlad Lishanlo": {"pos": "LW", "alt": "LW, RW, CM, LM, RM, LB, RB"},
    "Nurkabyl Sharipbay": {"pos": "ST", "alt": "CAM, RW, LW"},
    "Dastan Sadyraliyev": {"pos": "GK", "alt": ""},
    "Rauan Tanov": {"pos": "CM", "alt": "RM, LM, LW"},
    "Adok Salimzhan": {"pos": "CM", "alt": ""},
    "Assylbek Nurmagambetov": {"pos": "FWD", "alt": "CAM, RW, LW"},
    "Dias August": {"pos": "LW", "alt": "RB, RW, FWD"},
    "Yernar Bestikpayev": {"pos": "LB", "alt": "RB, CB, RW, LW"},
    "Aidyn Kassym": {"pos": "GK", "alt": ""},
    "Niyaz Bayankulov": {"pos": "CB", "alt": "RB, LB"},
    "Mirlan Toktoshev": {"pos": "RW", "alt": "CDM, LW, CM"},
    "Dias Kaibar": {"pos": "RW", "alt": "LW"},
    "Asset Khassan": {"pos": "CB", "alt": "LB, RB"},
    "Amir Rustam": {"pos": "RB", "alt": "RW, CM"},
    "Said Soltanzade": {"pos": "CM", "alt": "LW, CB, RB, LB, FWD, RW"},
    "Iosif Vassilenko": {"pos": "RB", "alt": "RW"},
    "Almas Kaneshev": {"pos": "CB", "alt": "CM"},
    "Aktan Abdullaatov": {"pos": "RB", "alt": "GK, LB, LW"},
    "Mansur Mutayev": {"pos": "FWD", "alt": "RW, LW"},
    "Aidyn Galymbekov": {"pos": "CM", "alt": "LB, RB, RW, LW"},
    "Raimbek Sarzhakov": {"pos": "FWD", "alt": "CAM, RW, LW, CM"},
    "Nurken Samigullin": {"pos": "RB", "alt": "LB, CM"},
    "Yeldos Ismailov": {"pos": "RW", "alt": "LW"},
    "Yernur Bauyrzhanuly": {"pos": "LB", "alt": "RB"},
    "Arsen Kudaibergen": {"pos": "FWD", "alt": ""},
    "Umid Kamilov": {"pos": "CB", "alt": "RB, LB, ST"},
    "Zhanibek Xenbek": {"pos": "LB", "alt": "RB, RW, LW"},
    "Alikhan Muratuly": {"pos": "CM", "alt": ""},
    "Nurislam": {"pos": "CM", "alt": "LB"},
    "Beka": {"pos": "CM", "alt": ""},
    "Daulet Bekmolda": {"pos": "CB", "alt": ""}
}

FAST_SET = {
    "Yernar Bestikpayev", "Akhmetov Dias", "Bakhtiyar Temirbayev", "Niyaz Bayankulov", "Daulet Bekmolda",
    "Dias August", "Adok Salimzhan", "Ansar Tanirbay", "Arsen Kudaibergen", "Medeu Yersain", "Yermakhan Borankhan",
    "Daryn Bakyrkhan", "Mukhammed A Askar", "Nurkabyl Sharipbay", "Nurken Samigullin", "Asset Khassan",
    "Mirlan Toktoshev", "Yeldos Ismailov", "Amir Rustam", "Zhanibek Xenbek", "Dias Bekbosyn"
}

POS_GRP = {
    "GK": "ВРТ", "CB": "ЗАЩ", "LB": "ЗАЩ", "RB": "ЗАЩ",
    "CM": "МИД", "CDM": "МИД", "CAM": "МИД", "LM": "МИД", "RM": "МИД",
    "FWD": "АТК", "LW": "АТК", "RW": "АТК", "ST": "АТК"
}
