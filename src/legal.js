import { CONTACT } from './data'

// Plain-language policies. Each section is a heading plus paragraphs; arrays inside `body` render as bullet lists.
export const LEGAL = {
  privacy: {
    path: '/privacy',
    title: 'Privacy Policy',
    updated: '31 October 2026',
    intro: `This policy explains what personal data Devliqly ("we", "us") collects through devliqly.in, why we collect it and how you can control it. It is written to meet India’s Digital Personal Data Protection Act, 2023 and the Information Technology Act, 2000.`,
    sections: [
      {
        h: 'Who we are',
        body: [
          'Devliqly is a technology studio based in India that designs and builds AI agents, chatbots and automation for businesses. For personal data you share with us through this website, Devliqly is the data fiduciary (controller).',
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
          'We do not use advertising or analytics cookies, and we do not knowingly collect data from children under 18.',
        ],
      },
      {
        h: 'How we use it',
        body: [
          [
            'To reply to your enquiry and schedule the demo you requested.',
            'To prepare proposals and deliver services you sign up for.',
            'To send you service-related updates about an engagement with us.',
            'To keep the website secure and prevent spam or abuse.',
          ],
          'We process this data on the basis of your consent when you submit a form or contact us, and for legitimate uses permitted by law. We never sell your personal data.',
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
          ],
          'Some of these providers store data outside India. We only share data with providers that offer appropriate safeguards, and we may disclose information where required by law.',
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
          'The site is served only over HTTPS, and access to enquiry data is limited to the people who need it. No method of transmission or storage is completely secure, but we take reasonable steps to protect your information.',
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
