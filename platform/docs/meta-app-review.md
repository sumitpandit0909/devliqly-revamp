# Meta App Review: becoming a Tech Provider

What to submit so the Devliqly Expo Agent app (ID 1664043868687217) gets advanced access to the two WhatsApp
permissions. With them, customers can connect their own WhatsApp Business number to the platform through Embedded
Signup, keeping the WhatsApp Business app on the same number (Coexistence).

Already done: business verification and the privacy policy (https://www.devliqly.in/privacy).

Submit in the App Dashboard → **App Review → Permissions and features**. Ask for **Advanced access** to
`whatsapp_business_messaging` and `whatsapp_business_management`. Each needs four parts: a use-case description, a
screen recording, a test API call and the data use checkup.

## Before recording

1. **Facebook Login for Business configuration.** App Dashboard → Facebook Login for Business → Configurations →
   Create configuration. Choose the **WhatsApp Embedded Signup** login variation and tick both WhatsApp permissions.
   Copy its **Configuration ID** into `META_SIGNUP_CONFIG_ID` in `.env`, and the app ID into `META_APP_ID`.
2. **Allowed domains.** Facebook Login for Business → Settings: add `https://platform.devliqly.in` and your ngrok
   address under "Allowed domains for the JavaScript SDK", and turn on "Login with the JavaScript SDK". Facebook's
   login only works over https, so test the button through ngrok or the live site, not `http://localhost`.
3. **Webhook fields.** WhatsApp → Configuration → Webhook fields: subscribe to `messages`, `account_update`,
   `history`, `smb_app_state_sync` and `smb_message_echoes`.
4. **Test API calls.** The "API precheck" step wants at least one successful call with each permission in the last
   30 days. Sending a card to Riya covers `whatsapp_business_messaging`. Opening the Follow-ups screen after
   connecting a number lists its templates, which covers `whatsapp_business_management`.

## whatsapp_business_messaging

**How we use it** (paste into the use-case box):

> Devliqly Platform is a CRM for companies exhibiting at trade shows. Their sales reps send photos of visitors'
> business cards to our WhatsApp number. Our app downloads the photo, reads the card, saves the person as a contact in
> that company's CRM and replies to the rep on WhatsApp with what it saved, so the rep can correct it there.
>
> Each customer company can also connect its own WhatsApp Business number through Embedded Signup. From that number we
> send one approved template message to visitors who agreed to hear from the company on WhatsApp, after the event. We
> record an opt-out when someone replies STOP and never message them again. We don't send marketing to people who
> haven't agreed, and we don't use WhatsApp data for advertising.

**Screen recording** (about 2 minutes, phone and computer both visible, or recorded one after the other):

1. On a phone, open WhatsApp and send a photo of a business card to the Devliqly number.
2. Show the reply arriving: the reaction, then the message listing the saved name, company, phone and email.
3. On the computer, log in to the CRM, open **Contacts** and show the new contact with the card photo.
4. Open **Follow-ups** and show the follow-up planned for that contact.
5. Say or caption: "Messages are sent by the Devliqly Platform through the WhatsApp Cloud API."

## whatsapp_business_management

**How we use it:**

> We use this permission to onboard a customer's WhatsApp Business account after they complete Embedded Signup in our
> CRM. With the token from Embedded Signup we: read the phone number they connected; subscribe our app to their
> account's webhooks so we receive replies and delivery updates; start the contacts and chat history sync that
> WhatsApp Business app numbers need; and list their approved message templates so they can choose the one used for
> follow-ups. We don't change their business profile, phone number settings or any other assets.

**Screen recording** (about 2 minutes):

1. Log in to the CRM as a company owner and open **Follow-ups**.
2. In "Your WhatsApp number", click **Connect WhatsApp**. The Meta pop-up opens.
3. Go through it: log in, choose the business, choose **connect your existing WhatsApp Business app**, enter the
   number, and approve the connection in the WhatsApp Business app on the phone. Show the phone screen for that step.
4. Back in the CRM, show the connected number, "History sync" progress and the list of approved templates.
5. Pick a template, tick WhatsApp follow-ups and save.

If no spare WhatsApp Business app number is available while recording, show the pop-up up to entering the number and
say so in the notes. Reviewers accept a partial flow less often, so a real number is better.

## Data use checkup

- **Data used:** business phone number, WhatsApp account ID, message content sent to our number, delivery statuses,
  and the contact details read from business cards.
- **Purpose:** providing the CRM and follow-up features the customer signed up for.
- **Shared with:** our processors only (hosting, database, AI that reads cards, email), as listed in the privacy policy.
- **Retention:** raw webhook data and job records are deleted after 30 days. Contacts stay until the customer deletes
  them. Data deletion instructions: https://www.devliqly.in/privacy#how-to-delete-your-data
- **No** selling of data, no advertising use, no access for law enforcement except where legally required.

## After approval

Meta may also ask you to accept the Tech Provider terms in the App Dashboard. After that, customers outside the
Devliqly business can use **Connect WhatsApp**. Limits for a new Tech Provider: 10 new customers per 7 days, 200 once
the business is verified, which it already is.
