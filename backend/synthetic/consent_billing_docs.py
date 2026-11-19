"""
backend/synthetic/consent_billing_docs.py
─────────────────────────────────────────
Generates 9 multilingual synthetic consent and billing documents:
  - 3 document types × 3 languages (en, es, hi)

Document types:
  consent_icu_admission     — ICU admission consent
  consent_surgery           — Surgical procedure consent
  billing_deductible_explanation — Deductible and copayment explanation

All text is entirely synthetic. No real patient names or identifiers are used.
Section markers use the pattern:  === SECTION: <name> ===
"""

from __future__ import annotations

from typing import Dict, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# Type aliases
# ─────────────────────────────────────────────────────────────────────────────
DocKey = Tuple[str, str]   # (doc_type, language)
DocRecord = Dict[str, str]  # {doc_type, language, title, content}


# ─────────────────────────────────────────────────────────────────────────────
# consent_icu_admission — ENGLISH
# ─────────────────────────────────────────────────────────────────────────────
_CONSENT_ICU_EN = """\
=== DOCUMENT: Intensive Care Unit Admission Consent ===
Hospital: Riverside General Medical Center
Version: 2024-A  |  Reference: FORM-ICU-001-EN

=== SECTION: Patient Rights ===
You have the right to receive information about your medical condition, the
proposed treatment plan, and any risks and benefits in a language you understand.
You have the right to accept or refuse any treatment at any time, and to designate
a healthcare proxy or power of attorney to make decisions on your behalf.

=== SECTION: Nature of Intensive Care ===
The Intensive Care Unit (ICU) is a specialized hospital department providing
continuous monitoring and treatment for patients with life-threatening or
potentially life-threatening conditions.  ICU care may include, but is not
limited to:
  - Mechanical ventilation (breathing machine support)
  - Central venous catheter placement (a tube inserted into a large vein)
  - Arterial line monitoring (continuous blood pressure measurement)
  - Administration of vasopressors (medications to support blood pressure)
  - Continuous cardiac monitoring
  - Renal replacement therapy (dialysis) if kidneys fail
  - Total parenteral nutrition (intravenous nutritional support)

=== SECTION: Risks and Benefits ===
Benefits: Intensive monitoring and prompt intervention may prevent deterioration
and save your life or prevent permanent organ damage.

Risks:  All invasive procedures carry inherent risks, including:
  - Infection at insertion sites (central line-associated bloodstream infection)
  - Blood clots (deep vein thrombosis or pulmonary embolism)
  - Adverse medication reactions
  - Ventilator-associated pneumonia
  - Delirium and cognitive changes associated with critical illness
  - Psychological distress (ICU-acquired anxiety, PTSD)

No procedure is performed without medical necessity. The care team will explain
each procedure before performing it whenever the patient's condition permits.

=== SECTION: Visitation and Communication ===
ICU visitation is managed to support patient recovery. Family members or
designated support persons may visit during scheduled hours. The clinical team
will provide regular updates to the patient's designated contact person.
Interpreter services are available at no additional charge.

=== SECTION: Advance Directives ===
If you have a living will, Do-Not-Resuscitate (DNR) order, or other advance
directive, please inform the nursing staff immediately so it can be incorporated
into your care plan. If you do not have an advance directive and wish to create
one, the hospital social worker can assist you.

=== SECTION: Consent Declaration ===
By acknowledging this document, I confirm that I have received, read (or had
read to me), and understood the information above.  I consent to ICU admission
and the initiation of necessary critical-care interventions as determined by my
treating physicians.  I understand that this consent does not waive any of my
patient rights, and that I may withdraw consent for any specific procedure at
any time I am able to communicate my wishes.

Signature Line: ________________________________  Date: __________
(Patient or Legally Authorized Representative)

Witness: ________________________________  Date: __________
"""

# ─────────────────────────────────────────────────────────────────────────────
# consent_icu_admission — SPANISH
# ─────────────────────────────────────────────────────────────────────────────
_CONSENT_ICU_ES = """\
=== DOCUMENTO: Consentimiento para Admisión a la Unidad de Cuidados Intensivos ===
Hospital: Centro Médico General Riverside
Versión: 2024-A  |  Referencia: FORM-UCI-001-ES

=== SECCIÓN: Derechos del Paciente ===
Usted tiene derecho a recibir información sobre su condición médica, el plan de
tratamiento propuesto y los riesgos y beneficios en un idioma que comprenda.
Tiene derecho a aceptar o rechazar cualquier tratamiento en cualquier momento, y
a designar un representante de atención médica o poder notarial para tomar
decisiones en su nombre.

=== SECCIÓN: Naturaleza de los Cuidados Intensivos ===
La Unidad de Cuidados Intensivos (UCI) es un departamento hospitalario
especializado que proporciona monitorización y tratamiento continuos para
pacientes con condiciones potencialmente mortales. La atención en UCI puede
incluir, entre otros:
  - Ventilación mecánica (soporte con máquina respiratoria)
  - Colocación de catéter venoso central
  - Monitorización de línea arterial (medición continua de la presión arterial)
  - Administración de vasopresores (medicamentos para mantener la presión arterial)
  - Monitorización cardíaca continua
  - Terapia de reemplazo renal (diálisis) si los riñones fallan
  - Nutrición parenteral total (soporte nutricional intravenoso)

=== SECCIÓN: Riesgos y Beneficios ===
Beneficios: La monitorización intensiva y la intervención oportuna pueden
prevenir el deterioro y salvar su vida o evitar daños permanentes a los órganos.

Riesgos: Todos los procedimientos invasivos conllevan riesgos inherentes:
  - Infección en los sitios de inserción
  - Coágulos de sangre (trombosis venosa profunda o embolia pulmonar)
  - Reacciones adversas a medicamentos
  - Neumonía asociada al ventilador
  - Delirio y cambios cognitivos asociados a la enfermedad crítica
  - Angustia psicológica (ansiedad adquirida en UCI, TEPT)

=== SECCIÓN: Visitas y Comunicación ===
Las visitas en UCI se gestionan para apoyar la recuperación del paciente. Los
servicios de interpretación están disponibles sin cargo adicional. El equipo
clínico proporcionará actualizaciones regulares a la persona de contacto designada.

=== SECCIÓN: Directivas Anticipadas ===
Si usted tiene un testamento vital, una orden de No Resucitar (DNR) u otra
directiva anticipada, informe al personal de enfermería de inmediato para que
pueda incorporarse a su plan de atención.

=== SECCIÓN: Declaración de Consentimiento ===
Al firmar este documento, confirmo que he recibido, leído (o se me ha leído) y
comprendido la información anterior. Consiento la admisión a la UCI y el inicio
de las intervenciones de cuidados críticos necesarias según lo determinen mis
médicos tratantes. Entiendo que este consentimiento no renuncia a ninguno de mis
derechos como paciente.

Firma: ________________________________  Fecha: __________
(Paciente o Representante Legal Autorizado)

Testigo: ________________________________  Fecha: __________
"""

# ─────────────────────────────────────────────────────────────────────────────
# consent_icu_admission — HINDI
# ─────────────────────────────────────────────────────────────────────────────
_CONSENT_ICU_HI = """\
=== दस्तावेज़: गहन चिकित्सा इकाई प्रवेश सहमति ===
अस्पताल: रिवरसाइड जनरल मेडिकल सेंटर
संस्करण: 2024-A  |  संदर्भ: FORM-ICU-001-HI

=== अनुभाग: रोगी के अधिकार ===
आपको अपनी चिकित्सा स्थिति, प्रस्तावित उपचार योजना तथा उससे संबंधित जोखिम और लाभ
के बारे में अपनी समझ की भाषा में जानकारी प्राप्त करने का अधिकार है। आप किसी भी समय
किसी भी उपचार को स्वीकार या अस्वीकार करने का अधिकार रखते हैं। आप किसी स्वास्थ्य
देखभाल प्रतिनिधि को भी नियुक्त कर सकते हैं।

=== अनुभाग: गहन चिकित्सा की प्रकृति ===
गहन चिकित्सा इकाई (ICU) एक विशेष अस्पताल विभाग है जो जीवन-घातक स्थितियों वाले
रोगियों के लिए निरंतर निगरानी और उपचार प्रदान करता है। ICU देखभाल में शामिल हो सकते हैं:
  - यांत्रिक वेंटिलेशन (श्वास-यंत्र सहायता)
  - केंद्रीय शिरापरक कैथेटर स्थापना
  - धमनी रेखा निगरानी (निरंतर रक्तचाप माप)
  - वैसोप्रेसर दवाओं का प्रशासन
  - निरंतर हृदय निगरानी
  - गुर्दे की प्रतिस्थापन चिकित्सा (डायलिसिस)
  - संपूर्ण अंतःशिरा पोषण

=== अनुभाग: जोखिम और लाभ ===
लाभ: गहन निगरानी और समय पर हस्तक्षेप से जीवन बचाया जा सकता है और स्थायी
अंग क्षति को रोका जा सकता है।

जोखिम: सभी आक्रामक प्रक्रियाओं में अंतर्निहित जोखिम होते हैं जैसे:
  - सम्मिलन स्थलों पर संक्रमण
  - रक्त के थक्के
  - दवा प्रतिकूल प्रतिक्रियाएं
  - वेंटिलेटर से जुड़ा निमोनिया
  - प्रलाप और संज्ञानात्मक परिवर्तन
  - मनोवैज्ञानिक संकट

=== अनुभाग: मुलाकात और संचार ===
ICU में मुलाकात रोगी की स्वास्थ्य लाभ प्रक्रिया का समर्थन करने के लिए प्रबंधित की जाती है।
दुभाषिया सेवाएं बिना किसी अतिरिक्त शुल्क के उपलब्ध हैं।

=== अनुभाग: अग्रिम निर्देश ===
यदि आपके पास लिविंग विल, DNR आदेश या कोई अन्य अग्रिम निर्देश है, तो कृपया तुरंत
नर्सिंग स्टाफ को सूचित करें।

=== अनुभाग: सहमति घोषणा ===
इस दस्तावेज़ को स्वीकार करके मैं पुष्टि करता/करती हूं कि मैंने उपरोक्त जानकारी प्राप्त
की, पढ़ी (या पढ़वाई गई) और समझी है। मैं ICU में प्रवेश और मेरे उपचार करने वाले
चिकित्सकों द्वारा निर्धारित आवश्यक महत्वपूर्ण देखभाल हस्तक्षेपों की शुरुआत के लिए
सहमति देता/देती हूं।

हस्ताक्षर: ________________________________  तारीख: __________
(रोगी या कानूनी रूप से अधिकृत प्रतिनिधि)

साक्षी: ________________________________  तारीख: __________
"""

# ─────────────────────────────────────────────────────────────────────────────
# consent_surgery — ENGLISH
# ─────────────────────────────────────────────────────────────────────────────
_CONSENT_SURGERY_EN = """\
=== DOCUMENT: Surgical Procedure Consent ===
Hospital: Riverside General Medical Center
Version: 2024-A  |  Reference: FORM-SRG-001-EN

=== SECTION: Proposed Procedure ===
You are being asked to consent to a surgical procedure. The specific procedure,
its medical indication, intended benefits, material risks, and available
alternatives will be explained by your surgeon prior to signing.  This form
documents your voluntary, informed decision after that explanation.

=== SECTION: Anesthesia ===
Surgical procedures typically require anesthesia (general, regional, local, or
sedation). Anesthesia carries its own set of risks independent of the surgery,
including:
  - Nausea and vomiting during recovery
  - Sore throat (from breathing tube placement during general anesthesia)
  - Allergic reactions to anesthetic agents
  - Rare: dental damage, awareness under anesthesia, nerve injury
  - Cardiovascular complications (abnormal heart rate or blood pressure)
  - In extremely rare cases: anesthesia-related death

An anesthesiologist or Certified Registered Nurse Anesthetist (CRNA) will
evaluate you before the procedure and address your questions.

=== SECTION: General Surgical Risks ===
In addition to procedure-specific risks disclosed by your surgeon, all surgical
interventions share general risks:
  - Bleeding (intraoperative or postoperative hemorrhage)
  - Surgical site infection (superficial or deep)
  - Blood clots (deep vein thrombosis; pulmonary embolism)
  - Injury to adjacent structures (nerves, vessels, organs)
  - Scarring or keloid formation
  - Prolonged recovery or need for reoperation
  - Adverse reaction to blood transfusion (if required)
  - Conversion from minimally invasive to open procedure

=== SECTION: Blood and Blood Products ===
If medically necessary, you may receive blood transfusions or blood products
during or after surgery. If you have religious or personal objections to
transfusion, you must notify your surgeon and the anesthesia team before the
procedure so alternative strategies can be planned.

=== SECTION: Implants and Medical Devices ===
If your procedure involves an implant (joint replacement, mesh, stent, pacemaker
lead, etc.), you will receive device information as required by applicable law.
Implant manufacturer and lot number will be documented in your operative record.

=== SECTION: Photographs and Recording ===
Surgical procedures may be photographed or video-recorded for clinical
documentation, quality assurance, or educational purposes. Identifiers are
removed before any educational use. You may decline recording for educational
purposes without affecting your care.

=== SECTION: Consent Declaration ===
I confirm that my surgeon has explained the proposed procedure, its purpose,
the material risks and benefits, and the available alternatives including no
treatment.  I have had the opportunity to ask questions and all my questions have
been answered to my satisfaction.  I voluntarily consent to the procedure.

Signature: ________________________________  Date: __________
(Patient or Legally Authorized Representative)

Surgeon: ________________________________  Date: __________
Witness: ________________________________  Date: __________
"""

# ─────────────────────────────────────────────────────────────────────────────
# consent_surgery — SPANISH
# ─────────────────────────────────────────────────────────────────────────────
_CONSENT_SURGERY_ES = """\
=== DOCUMENTO: Consentimiento para Procedimiento Quirúrgico ===
Hospital: Centro Médico General Riverside
Versión: 2024-A  |  Referencia: FORM-CIR-001-ES

=== SECCIÓN: Procedimiento Propuesto ===
Se le solicita su consentimiento para un procedimiento quirúrgico. Su cirujano
le explicará el procedimiento específico, su indicación médica, los beneficios
esperados, los riesgos relevantes y las alternativas disponibles antes de firmar.

=== SECCIÓN: Anestesia ===
Los procedimientos quirúrgicos generalmente requieren anestesia (general,
regional, local o sedación). La anestesia conlleva sus propios riesgos:
  - Náuseas y vómitos durante la recuperación
  - Dolor de garganta (por tubo de intubación durante anestesia general)
  - Reacciones alérgicas a agentes anestésicos
  - Raros: daño dental, consciencia bajo anestesia, lesión nerviosa
  - Complicaciones cardiovasculares (frecuencia cardíaca o presión arterial anormales)
  - En casos muy raros: muerte relacionada con la anestesia

Un anestesiólogo le evaluará antes del procedimiento.

=== SECCIÓN: Riesgos Quirúrgicos Generales ===
Además de los riesgos específicos del procedimiento, todas las intervenciones
quirúrgicas comparten riesgos generales:
  - Sangrado (hemorragia intraoperatoria o postoperatoria)
  - Infección del sitio quirúrgico
  - Coágulos de sangre (trombosis venosa profunda; embolia pulmonar)
  - Lesión de estructuras adyacentes (nervios, vasos, órganos)
  - Cicatrización o formación de queloides
  - Recuperación prolongada o necesidad de reoperación

=== SECCIÓN: Sangre y Hemoderivados ===
Si es médicamente necesario, puede recibir transfusiones de sangre o
hemoderivados. Si tiene objeciones religiosas o personales, debe notificarlo a
su cirujano antes del procedimiento para planificar estrategias alternativas.

=== SECCIÓN: Declaración de Consentimiento ===
Confirmo que mi cirujano ha explicado el procedimiento propuesto, su propósito,
los riesgos y beneficios relevantes, y las alternativas disponibles. He tenido
la oportunidad de hacer preguntas y todas han sido respondidas a mi satisfacción.
Consiento voluntariamente al procedimiento.

Firma: ________________________________  Fecha: __________
(Paciente o Representante Legal Autorizado)

Cirujano: ________________________________  Fecha: __________
Testigo: ________________________________  Fecha: __________
"""

# ─────────────────────────────────────────────────────────────────────────────
# consent_surgery — HINDI
# ─────────────────────────────────────────────────────────────────────────────
_CONSENT_SURGERY_HI = """\
=== दस्तावेज़: शल्य प्रक्रिया सहमति ===
अस्पताल: रिवरसाइड जनरल मेडिकल सेंटर
संस्करण: 2024-A  |  संदर्भ: FORM-SRG-001-HI

=== अनुभाग: प्रस्तावित प्रक्रिया ===
आपसे एक शल्य प्रक्रिया के लिए सहमति मांगी जा रही है। आपके सर्जन हस्ताक्षर करने से
पहले विशिष्ट प्रक्रिया, उसकी चिकित्सा संकेत, अपेक्षित लाभ, महत्वपूर्ण जोखिम और
उपलब्ध विकल्पों की व्याख्या करेंगे।

=== अनुभाग: संज्ञाहरण (एनेस्थीसिया) ===
शल्य प्रक्रियाओं में आमतौर पर संज्ञाहरण (सामान्य, क्षेत्रीय, स्थानीय या शामक) की
आवश्यकता होती है। संज्ञाहरण के अपने जोखिम हैं:
  - स्वास्थ्य लाभ के दौरान मतली और उल्टी
  - गले में दर्द (सामान्य संज्ञाहरण के दौरान श्वास नली स्थापना से)
  - संज्ञाहरण दवाओं से एलर्जी प्रतिक्रियाएं
  - दुर्लभ: दंत क्षति, संज्ञाहरण के तहत जागरूकता, तंत्रिका चोट
  - हृदय संबंधी जटिलताएं
  - अत्यंत दुर्लभ मामलों में: संज्ञाहरण से संबंधित मृत्यु

एक एनेस्थेसियोलॉजिस्ट प्रक्रिया से पहले आपका मूल्यांकन करेगा।

=== अनुभाग: सामान्य शल्य चिकित्सा जोखिम ===
  - रक्तस्राव (इंट्राऑपरेटिव या पोस्टऑपरेटिव रक्तस्राव)
  - शल्य स्थल संक्रमण
  - रक्त के थक्के (गहरी शिरा घनास्त्रता; फुफ्फुसीय अन्त:शल्यता)
  - आसन्न संरचनाओं को चोट (नसें, वाहिकाएं, अंग)
  - निशान या केलोइड गठन
  - लंबी वसूली या पुनर्संचालन की आवश्यकता

=== अनुभाग: रक्त और रक्त उत्पाद ===
यदि चिकित्सकीय रूप से आवश्यक हो, तो आपको सर्जरी के दौरान या बाद में रक्त आधान
या रक्त उत्पाद मिल सकते हैं। यदि आपको धार्मिक या व्यक्तिगत आपत्ति है, तो कृपया
प्रक्रिया से पहले अपने सर्जन को सूचित करें।

=== अनुभाग: सहमति घोषणा ===
मैं पुष्टि करता/करती हूं कि मेरे सर्जन ने प्रस्तावित प्रक्रिया, उसके उद्देश्य,
महत्वपूर्ण जोखिम और लाभ, और उपलब्ध विकल्पों की व्याख्या की है। मैंने प्रश्न
पूछने का अवसर पाया और सभी प्रश्नों के उत्तर मुझे संतोषजनक रूप से दिए गए।
मैं स्वेच्छा से प्रक्रिया के लिए सहमति देता/देती हूं।

हस्ताक्षर: ________________________________  तारीख: __________
(रोगी या कानूनी रूप से अधिकृत प्रतिनिधि)

सर्जन: ________________________________  तारीख: __________
साक्षी: ________________________________  तारीख: __________
"""

# ─────────────────────────────────────────────────────────────────────────────
# billing_deductible_explanation — ENGLISH
# ─────────────────────────────────────────────────────────────────────────────
_BILLING_EN = """\
=== DOCUMENT: Billing, Deductible & Copayment Explanation ===
Hospital: Riverside General Medical Center
Version: 2024-A  |  Reference: FORM-BIL-001-EN

=== SECTION: Overview ===
This document explains how your hospital bill is calculated, what your insurance
plan is expected to pay, and what you are responsible for paying out-of-pocket.
If you have questions, our Financial Counseling team is available Monday through
Friday, 08:00–17:00, at extension 4300.

=== SECTION: Glossary of Key Terms ===
Deductible:
  The amount you must pay for covered healthcare services before your insurance
  plan begins to pay.  Example: if your deductible is $2,000, you pay the first
  $2,000 of covered services each plan year; your insurer pays the rest
  (minus any applicable copayments or coinsurance).

Copayment (Copay):
  A fixed dollar amount you pay for a specific service (e.g., $50 for an ER
  visit) regardless of the total cost of that service.

Coinsurance:
  Your share of costs after you have met your deductible, expressed as a
  percentage.  Example: 20% coinsurance means you pay 20% of covered costs and
  your insurer pays 80%.

Out-of-Pocket Maximum:
  The maximum total amount you will pay in a plan year for covered services.
  Once you reach this limit, your insurer covers 100% of covered costs for the
  remainder of the plan year.

In-Network vs. Out-of-Network:
  In-network providers have contractual rates with your insurer; using them
  typically results in lower out-of-pocket costs. Out-of-network providers may
  result in higher costs or may not be covered at all, depending on your plan.

=== SECTION: Charge Categories ===
Your hospital bill may include charges in the following categories:
  - Room and board (daily inpatient rate; ICU rates differ from general ward rates)
  - Nursing and ancillary care services
  - Physician fees (may be billed separately by independent physician groups)
  - Operating room fees
  - Anesthesiology (typically billed separately)
  - Laboratory and diagnostic imaging
  - Pharmacy (medications administered during stay)
  - Medical supplies and disposables
  - Physical, occupational, or respiratory therapy
  - Discharge planning and social work services

=== SECTION: International Patients — Special Notice ===
If you are an international patient without U.S. insurance coverage, a deposit
based on estimated charges may be required before elective procedures. Payment
plans are available. Contact the International Patient Services office for
guidance on accepted currencies, wire transfer procedures, and coordination with
your home-country insurer.

=== SECTION: Financial Assistance ===
Riverside General Medical Center offers financial assistance programs for patients
who qualify based on income and family size. Applications are available at the
Admissions desk or at our website. Charity care, sliding-scale discounts, and
interest-free payment plans may be available. Financial assistance does not affect
the quality of care you receive.

=== SECTION: Itemized Bill Request ===
You have the right to request an itemized bill that lists every charge in detail.
Requests can be made at the Patient Billing office or in writing. Itemized bills
are provided at no charge within 30 days of the request.

=== SECTION: Dispute Resolution ===
If you believe a charge on your bill is incorrect, contact Patient Billing within
90 days of the statement date. We will investigate and respond within 15 business
days. If you are not satisfied, you may escalate the dispute to your state
insurance commissioner or the federal No Surprises Act dispute resolution process
(for applicable surprise billing situations).

=== SECTION: Acknowledgement ===
I acknowledge receipt of this billing explanation document and confirm that a
Financial Counselor has offered to review my specific coverage and estimated
patient responsibility with me.

Signature: ________________________________  Date: __________
"""

# ─────────────────────────────────────────────────────────────────────────────
# billing_deductible_explanation — SPANISH
# ─────────────────────────────────────────────────────────────────────────────
_BILLING_ES = """\
=== DOCUMENTO: Explicación de Facturación, Deducible y Copago ===
Hospital: Centro Médico General Riverside
Versión: 2024-A  |  Referencia: FORM-FAC-001-ES

=== SECCIÓN: Resumen ===
Este documento explica cómo se calcula su factura hospitalaria, lo que se espera
que pague su plan de seguro y lo que usted es responsable de pagar de su bolsillo.
Si tiene preguntas, nuestro equipo de Asesoría Financiera está disponible de lunes
a viernes, 08:00–17:00, en la extensión 4300.

=== SECCIÓN: Glosario de Términos Clave ===
Deducible:
  La cantidad que usted debe pagar por los servicios de salud cubiertos antes de
  que su plan de seguro comience a pagar. Ejemplo: si su deducible es $2,000,
  usted paga los primeros $2,000 de servicios cubiertos cada año del plan.

Copago:
  Una cantidad fija en dólares que paga por un servicio específico (p. ej., $50
  por una visita a urgencias), independientemente del costo total de ese servicio.

Coseguro:
  Su parte de los costos después de haber cumplido con su deducible, expresada
  como un porcentaje. Ejemplo: 20% de coseguro significa que usted paga el 20%
  de los costos cubiertos y su aseguradora paga el 80%.

Máximo de Desembolso Propio:
  El monto total máximo que pagará en un año del plan por servicios cubiertos.
  Una vez alcanzado este límite, su aseguradora cubre el 100% de los costos
  cubiertos por el resto del año del plan.

En Red vs. Fuera de Red:
  Los proveedores en red tienen tarifas contractuales con su aseguradora.
  El uso de proveedores fuera de red puede generar costos más altos.

=== SECCIÓN: Categorías de Cargos ===
Su factura hospitalaria puede incluir cargos en las siguientes categorías:
  - Habitación y manutención (tarifa diaria de hospitalización; las tarifas UCI
    difieren de las de sala general)
  - Servicios de enfermería y atención auxiliar
  - Honorarios médicos (pueden facturarse por separado)
  - Honorarios de quirófano
  - Anestesiología (generalmente facturada por separado)
  - Laboratorio y diagnóstico por imagen
  - Farmacia (medicamentos administrados durante la estancia)
  - Material médico y consumibles
  - Fisioterapia, terapia ocupacional o respiratoria
  - Planificación del alta y servicios de trabajo social

=== SECCIÓN: Pacientes Internacionales — Aviso Especial ===
Si usted es un paciente internacional sin cobertura de seguro en EE.UU., puede
requerirse un depósito basado en los cargos estimados antes de procedimientos
electivos. Se ofrecen planes de pago. Contacte la Oficina de Servicios para
Pacientes Internacionales para obtener orientación sobre monedas aceptadas,
procedimientos de transferencia bancaria y coordinación con su aseguradora en
su país de origen.

=== SECCIÓN: Asistencia Financiera ===
El Centro Médico General Riverside ofrece programas de asistencia financiera para
pacientes que califican según ingresos y tamaño familiar. Las solicitudes están
disponibles en el escritorio de Admisiones. Pueden estar disponibles atención
benéfica, descuentos por escala móvil y planes de pago sin intereses.

=== SECCIÓN: Solicitud de Factura Detallada ===
Tiene derecho a solicitar una factura detallada que enumere cada cargo en detalle.
Las solicitudes pueden realizarse en la Oficina de Facturación al Paciente o por
escrito. Las facturas detalladas se proporcionan sin cargo en un plazo de 30 días.

=== SECCIÓN: Acuse de Recibo ===
Acuso recibo de este documento explicativo de facturación y confirmo que un Asesor
Financiero se ha ofrecido a revisar mi cobertura específica y la responsabilidad
estimada del paciente conmigo.

Firma: ________________________________  Fecha: __________
"""

# ─────────────────────────────────────────────────────────────────────────────
# billing_deductible_explanation — HINDI
# ─────────────────────────────────────────────────────────────────────────────
_BILLING_HI = """\
=== दस्तावेज़: बिलिंग, कटौती योग्य राशि और सह-भुगतान की व्याख्या ===
अस्पताल: रिवरसाइड जनरल मेडिकल सेंटर
संस्करण: 2024-A  |  संदर्भ: FORM-BIL-001-HI

=== अनुभाग: अवलोकन ===
यह दस्तावेज़ बताता है कि आपका अस्पताल बिल कैसे गणना किया जाता है, आपकी बीमा योजना
से क्या भुगतान अपेक्षित है, और आपकी जेब से कितना भुगतान करना होगा। यदि आपके
प्रश्न हैं, तो हमारी वित्तीय परामर्श टीम सोमवार से शुक्रवार, 08:00–17:00, एक्सटेंशन
4300 पर उपलब्ध है।

=== अनुभाग: मुख्य शब्दों की शब्दावली ===
कटौती योग्य राशि (Deductible):
  वह राशि जो आपको बीमा योजना के भुगतान शुरू करने से पहले कवर किए गए स्वास्थ्य सेवाओं
  के लिए चुकानी होती है। उदाहरण: यदि आपकी कटौती $2,000 है, तो आप प्रत्येक योजना
  वर्ष में पहले $2,000 का भुगतान करते हैं।

सह-भुगतान (Copayment):
  किसी विशिष्ट सेवा के लिए आपके द्वारा भुगतान की जाने वाली एक निश्चित राशि
  (जैसे, ER विजिट के लिए $50)।

सह-बीमा (Coinsurance):
  कटौती योग्य राशि पूरी होने के बाद आपकी लागत का हिस्सा, प्रतिशत में। उदाहरण:
  20% सह-बीमा का मतलब है कि आप 20% का भुगतान करते हैं और बीमाकर्ता 80% देता है।

अधिकतम जेब खर्च (Out-of-Pocket Maximum):
  एक योजना वर्ष में कवर की गई सेवाओं के लिए आपके द्वारा भुगतान की जाने वाली अधिकतम
  कुल राशि। इस सीमा तक पहुंचने के बाद, बीमाकर्ता शेष वर्ष के लिए 100% का भुगतान करता है।

नेटवर्क में बनाम नेटवर्क के बाहर:
  नेटवर्क प्रदाताओं के पास आपके बीमाकर्ता के साथ संविदात्मक दरें होती हैं।

=== अनुभाग: शुल्क श्रेणियां ===
आपके अस्पताल बिल में निम्नलिखित श्रेणियों में शुल्क शामिल हो सकते हैं:
  - कमरा और बोर्ड (दैनिक इनपेशेंट दर)
  - नर्सिंग और सहायक देखभाल सेवाएं
  - चिकित्सक शुल्क
  - ऑपरेटिंग रूम शुल्क
  - संज्ञाहरण (Anesthesiology)
  - प्रयोगशाला और नैदानिक इमेजिंग
  - फार्मेसी (रहने के दौरान दी गई दवाएं)
  - चिकित्सा आपूर्ति और उपभोग्य वस्तुएं
  - भौतिक, व्यावसायिक, या श्वसन चिकित्सा

=== अनुभाग: अंतर्राष्ट्रीय रोगी — विशेष सूचना ===
यदि आप अमेरिकी बीमा कवरेज के बिना एक अंतर्राष्ट्रीय रोगी हैं, तो वैकल्पिक प्रक्रियाओं
से पहले अनुमानित शुल्क के आधार पर जमा राशि की आवश्यकता हो सकती है। भुगतान योजनाएं
उपलब्ध हैं। स्वीकृत मुद्राओं और आपके देश के बीमाकर्ता के साथ समन्वय के लिए
अंतर्राष्ट्रीय रोगी सेवा कार्यालय से संपर्क करें।

=== अनुभाग: वित्तीय सहायता ===
रिवरसाइड जनरल मेडिकल सेंटर उन रोगियों के लिए वित्तीय सहायता कार्यक्रम प्रदान करता है
जो आय और परिवार के आकार के आधार पर अर्हता प्राप्त करते हैं। धर्मार्थ देखभाल, स्लाइडिंग
स्केल छूट और ब्याज-मुक्त भुगतान योजनाएं उपलब्ध हो सकती हैं।

=== अनुभाग: स्वीकृति ===
मैं इस बिलिंग स्पष्टीकरण दस्तावेज़ की प्राप्ति स्वीकार करता/करती हूं और पुष्टि करता/करती
हूं कि एक वित्तीय परामर्शदाता ने मेरी विशिष्ट कवरेज और अनुमानित रोगी जिम्मेदारी की
समीक्षा करने का प्रस्ताव दिया है।

हस्ताक्षर: ________________________________  तारीख: __________
"""

# ─────────────────────────────────────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────────────────────────────────────
_DOCUMENTS: Dict[DocKey, DocRecord] = {
    ("consent_icu_admission", "en"): {
        "doc_type": "consent_icu_admission",
        "language": "en",
        "title": "Intensive Care Unit Admission Consent",
        "content": _CONSENT_ICU_EN,
    },
    ("consent_icu_admission", "es"): {
        "doc_type": "consent_icu_admission",
        "language": "es",
        "title": "Consentimiento para Admisión a la Unidad de Cuidados Intensivos",
        "content": _CONSENT_ICU_ES,
    },
    ("consent_icu_admission", "hi"): {
        "doc_type": "consent_icu_admission",
        "language": "hi",
        "title": "गहन चिकित्सा इकाई प्रवेश सहमति",
        "content": _CONSENT_ICU_HI,
    },
    ("consent_surgery", "en"): {
        "doc_type": "consent_surgery",
        "language": "en",
        "title": "Surgical Procedure Consent",
        "content": _CONSENT_SURGERY_EN,
    },
    ("consent_surgery", "es"): {
        "doc_type": "consent_surgery",
        "language": "es",
        "title": "Consentimiento para Procedimiento Quirúrgico",
        "content": _CONSENT_SURGERY_ES,
    },
    ("consent_surgery", "hi"): {
        "doc_type": "consent_surgery",
        "language": "hi",
        "title": "शल्य प्रक्रिया सहमति",
        "content": _CONSENT_SURGERY_HI,
    },
    ("billing_deductible_explanation", "en"): {
        "doc_type": "billing_deductible_explanation",
        "language": "en",
        "title": "Billing, Deductible & Copayment Explanation",
        "content": _BILLING_EN,
    },
    ("billing_deductible_explanation", "es"): {
        "doc_type": "billing_deductible_explanation",
        "language": "es",
        "title": "Explicación de Facturación, Deducible y Copago",
        "content": _BILLING_ES,
    },
    ("billing_deductible_explanation", "hi"): {
        "doc_type": "billing_deductible_explanation",
        "language": "hi",
        "title": "बिलिंग, कटौती योग्य राशि और सह-भुगतान की व्याख्या",
        "content": _BILLING_HI,
    },
}


def generate_consent_billing_docs() -> Dict[DocKey, DocRecord]:
    """
    Return all 9 synthetic multilingual consent/billing documents as a dict.

    Keys are (doc_type, language) tuples.
    Values are dicts matching the /documents/{doc_type}/{language} API contract.
    """
    assert len(_DOCUMENTS) == 9, f"Expected 9 documents, got {len(_DOCUMENTS)}"
    return dict(_DOCUMENTS)


def get_document(doc_type: str, language: str) -> DocRecord | None:
    """Return a single document by type and language, or None if not found."""
    return _DOCUMENTS.get((doc_type, language))


SUPPORTED_DOC_TYPES = ["consent_icu_admission", "consent_surgery", "billing_deductible_explanation"]
SUPPORTED_LANGUAGES = ["en", "es", "hi"]


if __name__ == "__main__":
    docs = generate_consent_billing_docs()
    for (dt, lang), doc in docs.items():
        print(f"[{dt} / {lang}] — {len(doc['content'])} chars")
