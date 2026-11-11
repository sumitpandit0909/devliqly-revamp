import { CONTACT } from './data'

// Plain-language policies. Each section is a heading plus paragraphs; arrays inside `body` render as bullet lists.
export const LEGAL = {
  privacy: {
    path: '/privacy',
    title: 'Privacy Policy',
    updated: '11 November 2026',
    intro: `This policy explains what personal data Devliqly ("we", "us") collects through devliqly.in and through the Devliqly Platform, including our WhatsApp agent, why we collect it and how you can control it. It is written to meet India’s Digital Personal Data Protection Act, 2023 and the Information Technology Act, 2000.`,
    sections: [
      {
        h: 'Who we are',
        body: [
          'Devliqly is a technology studio based in India that designs and builds AI agents, chatbots and automation for businesses. We also run the Devliqly Platform at platform.devliqly.in, a CRM with a WhatsApp agent that helps sales teams capture leads at events.',
          'For personal data you share with us through this website, and for the account and billing details of businesses that use our services, Devliqly is the data fiduciary (controller). For data a business puts into the Devliqly Platform about its own staff and prospects, that business is the data fiduciary and we process the data on its behalf.',
        ],
      },
      {
        h: 'What we collect',
        body: [
          'We only collect what you choose to give us, and a minimum of technical data needed to run the site:',
          [
            'Contact and demo forms: your name, email address, phone number, company, the service you are interested in, your preferred demo date and time, and your message.',
            'Email, phone and WhatsApp: whatever you share with us when you contact us directly.',
            'Technical data: our hosting provider processes standard server logs such as IP address, browser type and pages requested, for security and reliability.',
          ],
          'We do not use advertising or analytics cookies, and we do not knowingly collect data from children under 18. The Devliqly Platform uses a login cookie, which is needed to keep you signed in.',
        ],
      },
      {
        h: 'Devliqly Platform and WhatsApp agent',
        body: [
          'Businesses use the Devliqly Platform so their sales representatives can send business cards, notes and voice notes to our WhatsApp agent, which saves them as leads in the business’s CRM. When a business uses the Platform, we process:',
          [
            'Staff accounts: name, email address, WhatsApp number, role, company and login sessions.',
            'WhatsApp messages sent to the agent: the sender’s number and profile name, message text, photos, voice notes and their transcripts, timestamps and delivery status.',
            'Details of people the business meets (prospects): whatever appears on a business card or in a representative’s note, such as name, job title, company, phone number, email address, website and address, along with the card photo, notes about the conversation, follow-up history and marketing preferences.',
            'Usage records: activity logs, plan usage and the estimated cost of processing.',
          ],
          'We use this data to read cards and voice notes, create and update leads, reply to representatives, show the business its CRM, send the follow-ups the business has switched on, and keep the service secure. We do not sell this data and we do not use it to train our own AI models.',
          'Follow-up messages are sent on behalf of the business. WhatsApp follow-ups only go to people recorded as having agreed to receive them; a scanned business card does not count as agreement. Replying STOP on WhatsApp, or using the unsubscribe link in an email, stops further follow-ups.',
        ],
      },
      {
        h: 'Data we receive from Meta and WhatsApp',
        body: [
          'The Devliqly Platform uses the WhatsApp Business Platform, a service of Meta Platforms. When a business connects its WhatsApp number to the Platform, including by signing in through Facebook, we receive and store:',
          [
            'Identifiers for its business portfolio, WhatsApp Business account and phone number, and its business and display names.',
            'An access token that lets us send and receive messages for that number.',
            'Messages sent to and from that number, delivery status and message template details.',
            'If the business keeps using the WhatsApp Business app on the same number and chooses to share it: its WhatsApp contacts, up to the last six months of one-to-one chat history, and new messages it sends from the app. Group chats are not shared with us.',
          ],
          'We use this data only to provide the Platform to that business: sending and receiving its messages, showing them in its CRM and managing its templates. We do not receive Facebook passwords, and we do not use this data for advertising, sell it or share it except as described in this policy. WhatsApp and Meta also process messages under their own terms and privacy policies.',
        ],
      },
      {
        h: 'How we use it',
        body: [
          [
            'To reply to your enquiry and schedule the demo you requested.',
            'To prepare proposals and deliver services you sign up for.',
            'To send you service-related updates about an engagement with us.',
            'To keep the website and the Platform secure and prevent spam or abuse.',
          ],
          'We process this data on the basis of your consent when you submit a form or contact us, on the instructions of the business using the Platform, and for legitimate uses permitted by law. We never sell your personal data.',
        ],
      },
      {
        h: 'Who we share it with',
        body: [
          'We use a small number of service providers who process data on our behalf and only for the purposes above:',
          [
            'FormSubmit (formsubmit.co), which delivers website form submissions to our inbox.',
            'Vercel, which hosts this website.',
            'Google Fonts, which serves the typefaces used on the site.',
            'Email and messaging providers we use to correspond with you.',
            'Meta Platforms (WhatsApp Business Platform), which carries WhatsApp messages.',
            'Google (Gemini) and Anthropic (Claude), which read card photos and voice notes and help interpret messages.',
            'Render and Neon, which host the Platform’s application and database in Singapore.',
            'Cloudflare, which stores card photos in private storage and serves website images.',
            'Resend, which delivers emails sent by the Platform.',
          ],
          'Some of these providers store or process data outside India, including in Singapore and the United States. We only share data with providers that offer appropriate safeguards, and we may disclose information where required by law. If our business changes hands, data may transfer to the new owner under this policy.',
        ],
      },
      {
        h: 'Data from AI agents we build for clients',
        body: [
          'When we build or operate an AI agent for a client, conversations, call recordings and other data handled by that agent belong to the client. The client is the data fiduciary for its customers, and we process that data only on the client’s instructions under a separate agreement. If you spoke with an agent on a business’s website or phone line, please contact that business about your data.',
        ],
      },
      {
        h: 'How long we keep it',
        body: [
          'We keep enquiry data for as long as needed to respond and follow up, and for up to 24 months afterwards unless you ask us to delete it sooner. Data related to a contract is kept for as long as the law requires.',
          'On the Devliqly Platform, raw WhatsApp webhook data and background job records are deleted after 30 days. Leads, card photos and chats are kept while the business uses the Platform, until the business deletes them or asks us to. A record of people who opted out is kept so we can keep honouring that choice.',
        ],
      },
      {
        h: 'How to delete your data',
        body: [
          'You can ask us to delete your data at any time, without needing an account:',
          [
            `Email ${CONTACT.legal} with the subject "Data deletion" and include the phone number or email address the data is linked to. We will confirm your request and complete it within 30 days, except for anything the law requires us to keep.`,
            'If a business scanned your card or contacted you through the Platform, you can also ask that business directly. Businesses can erase a person, including their card photos and related chats, from the CRM. If you write to us instead, we will act on it with that business.',
            'If you connected a WhatsApp number through Facebook, you can disconnect it in the WhatsApp Business app or in Meta Business Suite, and remove Devliqly under Business Integrations in your Facebook settings. Then email us to have the data we received deleted.',
            'To stop WhatsApp follow-ups, reply STOP. To stop follow-up emails, use the unsubscribe link in the email.',
          ],
        ],
      },
      {
        h: 'Your rights',
        body: [
          'You can ask us to:',
          [
            'Tell you what personal data we hold about you and how it is used.',
            'Correct, complete or update inaccurate data.',
            'Erase your data, or withdraw consent you gave earlier.',
            'Nominate another person to exercise your rights in case of death or incapacity.',
          ],
          `Email ${CONTACT.legal} and we will respond within 30 days. If you are not satisfied with our response, you may complain to the Data Protection Board of India.`,
        ],
      },
      {
        h: 'Security',
        body: [
          'The site and the Platform are served only over HTTPS, and access to enquiry data is limited to the people who need it. On the Platform, each business’s data is kept separate from other businesses, card photos are held in private storage, and incoming WhatsApp events are checked to confirm they came from Meta. No method of transmission or storage is completely secure, but we take reasonable steps to protect your information.',
        ],
      },
      {
        h: 'Changes to this policy',
        body: [
          'We may update this policy from time to time. The date at the top shows when it last changed, and significant changes will be highlighted on this page.',
        ],
      },
      {
        h: 'Contact',
        body: [
          `Grievance and privacy requests: ${CONTACT.legal}. General enquiries: ${CONTACT.email} or ${CONTACT.phone}.`,
        ],
      },
    ],
  },

  terms: {
    path: '/terms',
    title: 'Terms & Conditions',
    updated: '31 October 2026',
    intro: 'These terms govern your use of devliqly.in. By using the website you agree to them. Work we do for you is covered by a separate proposal or agreement, which takes priority over these terms where they differ.',
    sections: [
      {
        h: 'About us',
        body: [
          'Devliqly is a technology studio based in India that builds AI agents, chatbots, voice and call agents, and custom automation workflows for businesses.',
        ],
      },
      {
        h: 'Using this website',
        body: [
          'You may use this website to learn about our services and to contact us. You agree not to:',
          [
            'Submit false, misleading or someone else’s information through our forms.',
            'Send spam, malware or anything unlawful through the website.',
            'Attempt to disrupt, overload or gain unauthorised access to the site or its infrastructure.',
            'Copy or scrape the site’s content for commercial use without permission.',
          ],
        ],
      },
      {
        h: 'Information on the site',
        body: [
          'Descriptions, examples and figures on this website are for general information. Results such as automation rates or response times vary by business and are illustrative, not guarantees. Pricing, scope and timelines are confirmed only in a written proposal.',
        ],
      },
      {
        h: 'Demos and enquiries',
        body: [
          'Requesting a demo or sending an enquiry does not create a contract. A demo slot is confirmed only when we reply to confirm it. We may decline any request at our discretion.',
        ],
      },
      {
        h: 'Client projects',
        body: [
          'When you engage us, the proposal or service agreement sets out scope, fees, payment terms, intellectual property, confidentiality and support. Unless that agreement says otherwise:',
          [
            'You own the content, data and knowledge you provide, and the conversations your agents handle.',
            'You are responsible for having the necessary consents to contact, record and process data of the people your agents interact with, including consent and DND rules for outbound calls and messages.',
            'AI systems can make mistakes. You are responsible for reviewing how agents are configured and for deciding which actions they may take without human approval.',
            'Third-party services such as telephony, messaging and AI model providers are subject to their own terms and charges.',
          ],
        ],
      },
      {
        h: 'Intellectual property',
        body: [
          'The design, text, graphics, code and branding of this website belong to Devliqly unless stated otherwise. Third-party names and logos mentioned on the site belong to their owners and are used only to describe integrations.',
        ],
      },
      {
        h: 'Third-party links',
        body: [
          'The site may link to other websites or services such as WhatsApp. We are not responsible for their content or practices.',
        ],
      },
      {
        h: 'Limitation of liability',
        body: [
          'The website is provided “as is”. To the extent permitted by law, Devliqly is not liable for any indirect or consequential loss arising from your use of the website. Nothing in these terms limits liability that cannot be limited under Indian law.',
        ],
      },
      {
        h: 'Privacy',
        body: [
          'Our Privacy Policy explains how we handle personal data you share through this website.',
        ],
      },
      {
        h: 'Governing law',
        body: [
          'These terms are governed by the laws of India. Any dispute will be subject to the exclusive jurisdiction of the courts of New Delhi, India.',
        ],
      },
      {
        h: 'Changes',
        body: [
          'We may update these terms from time to time. The date at the top shows when they last changed. Continued use of the website after changes means you accept the updated terms.',
        ],
      },
      {
        h: 'Contact',
        body: [
          `Questions about these terms: ${CONTACT.legal}. General enquiries: ${CONTACT.email} or ${CONTACT.phone}.`,
        ],
      },
    ],
  },
}
