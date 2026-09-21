/**
 * English / हिन्दी strings.
 *
 * A day of work with a string table, and for a Government of India deliverable
 * it is a visible signal of who this was built for.
 */
export const STRINGS = {
  en: {
    title: 'SHRUTI',
    subtitle: 'blind signal exploitation — samples to bits',
    drop: 'Drop an .IQ, .wav or SigMF file here',
    dropHint:
      'No sample rate, data type or centre frequency required — everything is inferred',
    analysing: 'Analysing',
    verdict: 'Verdict',
    container: 'Container',
    physical: 'Physical layer',
    waveform: 'Waveform',
    framing: 'Frame structure',
    payload: 'Payload',
    capabilities: 'Capabilities',
    spectrum: 'Spectrum',
    waterfall: 'Waterfall (time–frequency)',
    constellation: 'Constellation',
    entropy: 'Per-bit entropy profile',
    notes: 'How this was determined',
    cartridges: 'Waveform library',
    selftest: 'Blind self-test',
    runSelfTest: 'Randomise & run',
    yourSentence: 'Type any sentence',
    gated: 'Disabled — not enough data',
    identified: 'IDENTIFIED',
    probable: 'PROBABLE',
    unknown: 'UNKNOWN',
    unknownHelp:
      'SHRUTI does not explain this signal. Every measurement it could make is still shown below.',
    whatWouldResolve: 'What would resolve it',
    reencode: 're-encode agreement',
    symbols: 'symbols',
    bits: 'bits',
    header: 'header',
    selectionHint: 'Click a field or drag a plot — every view follows',
    analyse: 'Analyse',
    sampleRate: 'sample rate',
    inferred: 'inferred',
  },
  hi: {
    title: 'श्रुति',
    subtitle: 'अंध संकेत विश्लेषण — नमूनों से बिट्स तक',
    drop: 'यहाँ .IQ, .wav या SigMF फ़ाइल डालें',
    dropHint:
      'नमूना दर, डेटा प्रकार या केंद्र आवृत्ति की आवश्यकता नहीं — सब कुछ अनुमानित है',
    analysing: 'विश्लेषण जारी',
    verdict: 'निर्णय',
    container: 'कंटेनर',
    physical: 'भौतिक परत',
    waveform: 'तरंगरूप',
    framing: 'फ़्रेम संरचना',
    payload: 'पेलोड',
    capabilities: 'क्षमताएँ',
    spectrum: 'स्पेक्ट्रम',
    waterfall: 'वॉटरफ़ॉल (समय–आवृत्ति)',
    constellation: 'कॉन्स्टेलेशन',
    entropy: 'प्रति-बिट एन्ट्रॉपी',
    notes: 'यह कैसे निर्धारित हुआ',
    cartridges: 'तरंगरूप संग्रह',
    selftest: 'अंध स्व-परीक्षण',
    runSelfTest: 'यादृच्छिक करें और चलाएँ',
    yourSentence: 'कोई भी वाक्य लिखें',
    gated: 'अक्षम — पर्याप्त डेटा नहीं',
    identified: 'पहचाना गया',
    probable: 'संभावित',
    unknown: 'अज्ञात',
    unknownHelp:
      'श्रुति इस संकेत की व्याख्या नहीं कर सकती। जो माप संभव थे वे नीचे दिए गए हैं।',
    whatWouldResolve: 'इसे क्या हल करेगा',
    reencode: 'पुनः-एन्कोड सहमति',
    symbols: 'प्रतीक',
    bits: 'बिट्स',
    header: 'हेडर',
    selectionHint: 'किसी फ़ील्ड पर क्लिक करें — सभी दृश्य अनुसरण करेंगे',
    analyse: 'विश्लेषण करें',
    sampleRate: 'नमूना दर',
    inferred: 'अनुमानित',
  },
} as const

export type Lang = keyof typeof STRINGS
export type Key = keyof (typeof STRINGS)['en']
export const t = (lang: Lang, key: Key): string =>
  (STRINGS[lang] as Record<string, string>)[key] ?? STRINGS.en[key]
