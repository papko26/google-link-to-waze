# google-link-to-waze

**Translate Google Maps links into Waze-friendly coordinates in no time!**

---

## Motivation

Have you ever been running late and someone sends you a Google Maps link? You're frantically trying to extract the coordinates and transfer them into Waze, but you just don't have the time to figure it out. Frustrated and out of options, you give up and end up following the route on Google Maps, hoping for the best.

You finally arrive... at a field in the middle of nowhere. Google swears you're on a six-lane highway, but the only lanes in sight are made of grass.

Sound familiar?

Then this is exactly what you need!

---

## How It Works

1. Copy the Google Maps link you've been sent.
2. Paste it into (not yet, coming soon) [waze.papko.org](https://waze.papko.org).
3. Click the button and you'l be redirected to Waze

This stack hosts a web server that translates Google Maps links into Waze-compatible destinations. No more guesswork, no more detours—just navigation made simple.

---

## Disclaimers

### To the amazing folks at Waze:  
If you're reading this, please know that I admire your work. This little project is my humble attempt to make things easier for Waze users.

If you have any concerns—whether it’s about the code, the license, or anything else—don’t hesitate to reach out. I’m more than happy to work with you, transfer this project to you free of charge, and even dedicate a day or two to integrate it into your systems. Or, if you prefer, I can quietly remove it without a trace. Your wish is my command.

### To the amazing folks at Google:
If you're reading this, please know that your tools are an integral part of daily life for millions. This project isn't meant to undermine your incredible work, but rather to address a small gap in compatibility for those of us who rely on both Google Maps and Waze.
Same as for Wazers - feel free to reach me you have any concerns.

---

## Stack

- **Backend and Frontend**: Python (Flask) for logic and HTML rendering (contributions are always welcome)
- **Reverse Proxy**: NGINX  
- **SSL**: Managed via Certbot (Let’s Encrypt)  
- **Containerized**: Docker Compose orchestrating the magic  

---

## How to Contribute

Contributions, ideas, and constructive criticism are always welcome! Head over to the [GitHub repository](https://github.com/papko26/google-link-to-waze) and feel free to submit a pull request or file an issue.

---

## License

This project is open-source under the MIT License. See the [LICENSE](./LICENSE) file for details.

---

## The Fine Print

This project is not affiliated with Google, Waze, or any related entities. It's a papko-driven effort born out of frustration with GPS woes and a desire to make life a little easier for us all.