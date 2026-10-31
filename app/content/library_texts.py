"""Authored manuscripts for the ready-to-print library (EN / DE / ES).

One story, three languages, page-aligned sentence by sentence so the bilingual editions
can be built without any machine translation at render time. Written for the 3-5 band:
two or three read-aloud sentences per page, present tense, one concrete image per page.
"""

REFRAIN = {
    "en": "Hold the light, small one.",
    "de": "Halt das Licht, Kleine.",
    "es": "Sostén la luz, pequeña.",
}

TITLES = {
    "en": "Luna and the Lantern Forest",
    "de": "Luna und der Wald der Laternen",
    "es": "Luna y el Bosque de las Linternas",
}

SUBTITLES = {
    "en": "A story about courage, light and sharing",
    "de": "Eine Geschichte über Mut, Licht und Teilen",
    "es": "Una historia sobre el valor, la luz y el compartir",
}

STORY: dict[str, list[str]] = {
    "en": [
        "The forest keeps its light in lanterns. Every evening Luna walks the path and counts them: twelve warm lanterns, and one that stays dark all night.",
        "The dark lantern stands at the edge of the clearing, where the grass grows tall and the air smells of wet moss and cold stone.",
        "Luna asks the grown-ups about it. They smile and say the dark lantern has always been dark, and always will be, and that is simply how it is.",
        "One evening something small hums inside the dark lantern. It is a low sound like a bell underwater, quiet and patient, and it does not stop.",
        "Hold the light, small one. The hum says it again, softer now, as if it has waited a long time for somebody small enough to listen.",
        "Luna looks at the path home. The path is smooth and warm, the kitchen window is already glowing, and nobody would ever know she had been away.",
        "The grown-ups said leave it alone. The path is safe. But the hum is still there, thin and steady, asking for something Luna cannot name yet.",
        "She puts both hands in her pockets and takes one slow step backwards. Then another, and another, away from the tall grass and the dark lantern.",
        "At breakfast she cannot stop thinking about it. She packs bread, a rope, and the little brass lantern her grandmother gave her last summer, and she ties the rope twice around her waist.",
        "She kneels in the wet grass and reaches for the dark lantern. Her fingers slip on the cold metal and the brass lantern rolls away into the ferns.",
        "Now there are two dark lanterns. Luna sits in the grass with muddy knees and a stinging hand, and the evening comes down much faster than she expected.",
        "The clearing turns grey. The twelve warm lanterns look far away, like windows in a house she is not allowed to enter tonight, no matter how hard she knocks.",
        "The cold comes up through the ground and into her hands. Luna holds her knees, listens to nothing at all, and waits for the grey to pass.",
        "Maybe the light was never meant for small hands. Maybe the grown-ups were right, and the dark lantern is simply dark, and that is the end of it.",
        "Then Pip leans close, warm as a pocket. Pip is a lantern spirit, small and bright, and Pip does not argue. Hold the light, small one.",
        "Pip hums the three notes again, and Luna finally sees it: her own lantern never went out. It is only lying in the ferns, still glowing quietly.",
        "Luna picks it up and brushes off the leaves. The empty lantern is bigger than she thought, and the way to fill it is not what she expected at all.",
        "She does not keep the light for herself. She holds her brass lantern out over the empty one and lets the little flame lean across the gap.",
        "Her own lantern burns lower and lower. The clearing holds its breath. Then the dark lantern answers with light that spills across the wet grass.",
        "One by one the other lanterns lean closer. Warm light runs over the stones, the puddles shine like coins, and the evening smells of resin and bread.",
        "Hold the light, small one. Now the whole forest says it, in twelve small voices and one brand-new voice that has never spoken before, and it sounds exactly like her own.",
        "The neighbours come out with warm bread and quiet hands. Nobody says the lesson out loud, and everybody in the clearing understands it anyway, all at the same moment.",
        "That night Luna counts the lanterns again. Thirteen lanterns glow beside the path, and the tall grass smells of rain, moss and the warm light of thirteen lanterns.",
        "Before she sleeps she leaves the gate open a little, just in case somebody small comes looking for a light of their own tonight, the way she did.",
    ],
    "de": [
        "Der Wald bewahrt sein Licht in Laternen. Jeden Abend geht Luna den Weg entlang und zählt sie: zwölf warme Laternen und eine, die die ganze Nacht dunkel bleibt.",
        "Die dunkle Laterne steht am Rand der Lichtung, dort wo das Gras hoch wächst und die Luft nach nassem Moos, nach Regen und kaltem Stein riecht.",
        "Luna fragt die Erwachsenen danach. Sie lächeln und sagen, die dunkle Laterne sei schon immer dunkel gewesen, und so sei es eben, und dabei bleibt es.",
        "Eines Abends summt etwas Kleines in der dunklen Laterne. Es klingt wie eine Glocke unter Wasser, leise und geduldig, und es hört einfach nicht auf, auch dann nicht, als sie näher kommt.",
        "Halt das Licht, Kleine. Das Summen sagt es noch einmal, weicher jetzt, als hätte es lange auf jemanden gewartet, der klein genug ist, um zuzuhören.",
        "Luna schaut zum Weg nach Hause. Der Weg ist glatt und warm, im Küchenfenster brennt schon Licht, und niemand würde je erfahren, dass sie dort gewesen war.",
        "Die Erwachsenen haben gesagt, lass es in Ruhe. Der Weg ist sicher. Aber das Summen ist noch da, dünn und gleichmäßig, und fragt nach etwas, das Luna noch nicht benennen kann.",
        "Sie steckt beide Hände in die Taschen und macht einen langsamen Schritt rückwärts. Dann noch einen, und noch einen, weg vom hohen Gras und der dunklen Laterne.",
        "Beim Frühstück muss sie immerzu daran denken. Sie packt Brot ein, ein Seil und die kleine Messinglaterne, die ihr die Großmutter im letzten Sommer geschenkt hat.",
        "Sie kniet ins nasse Gras und greift nach der dunklen Laterne. Ihre Finger rutschen am kalten Metall ab, und die Messinglaterne rollt in die Farne davon.",
        "Jetzt gibt es zwei dunkle Laternen. Luna sitzt mit schmutzigen Knien und brennender Hand im Gras, und der Abend kommt viel schneller herab, als sie dachte.",
        "Die Lichtung wird grau. Die zwölf warmen Laternen wirken weit weg, wie Fenster in einem Haus, das sie heute Abend nicht betreten darf, so oft sie auch anklopft.",
        "Die Kälte steigt durch den Boden bis in ihre Hände. Luna umfasst die Knie, hört auf gar nichts und wartet, dass das Grau endlich weiterzieht.",
        "Vielleicht war das Licht nie für kleine Hände gedacht. Vielleicht hatten die Erwachsenen recht, die dunkle Laterne ist einfach dunkel, und das ist das Ende der Geschichte.",
        "Da lehnt sich Pip an sie, warm wie eine Tasche. Pip ist ein Laternengeist, klein und hell, und Pip diskutiert nicht. Halt das Licht, Kleine.",
        "Pip summt die drei Töne noch einmal, und Luna sieht es endlich: ihre eigene Laterne ist nie erloschen. Sie liegt nur zwischen den Farnen und leuchtet still weiter.",
        "Luna hebt sie auf und streift die Blätter ab. Die leere Laterne ist größer, als sie dachte, und der Weg, sie zu füllen, ist ganz anders als erwartet.",
        "Sie behält das Licht nicht für sich. Sie hält ihre Messinglaterne über die leere Laterne und lässt die kleine Flamme ganz langsam über den Spalt hinüberneigen.",
        "Ihre eigene Laterne brennt tiefer und tiefer. Die Lichtung hält den Atem an. Dann antwortet die dunkle Laterne mit Licht, das über das nasse Gras fließt.",
        "Eine nach der anderen rücken die Laternen näher. Warmes Licht läuft über die Steine, die Pfützen glänzen wie Münzen, und der Abend riecht nach Harz und Brot.",
        "Halt das Licht, Kleine. Jetzt sagt es der ganze Wald, mit zwölf kleinen Stimmen und einer ganz neuen Stimme, die noch nie gesprochen hat und die genau wie ihre eigene klingt.",
        "Die Nachbarn kommen mit warmem Brot und ruhigen Händen heraus. Niemand sagt die Lehre laut, und trotzdem verstehen sie alle auf der Lichtung, im selben Augenblick.",
        "In dieser Nacht zählt Luna die Laternen wieder. Dreizehn Laternen leuchten neben dem Weg, und das hohe Gras riecht nach Regen, Moos und warmem Licht.",
        "Bevor sie schläft, lässt sie das Tor ein Stück offen, nur für den Fall, dass jemand Kleines heute Nacht sein eigenes Licht sucht, so wie sie.",
    ],
    "es": [
        "El bosque guarda su luz en linternas. Cada tarde Luna recorre el sendero y las cuenta: doce linternas cálidas y una que sigue apagada toda la noche.",
        "La linterna apagada está en el borde del claro, donde la hierba crece alta y el aire huele a musgo mojado y a piedra fría.",
        "Luna pregunta a los adultos. Ellos sonríen y dicen que la linterna apagada siempre ha estado apagada, que siempre lo estará y que así son las cosas.",
        "Una tarde algo pequeño zumba dentro de la linterna apagada. Suena como una campana bajo el agua, callada y paciente, y no se detiene nunca.",
        "Sostén la luz, pequeña. El zumbido lo dice otra vez, más suave, como si llevara mucho tiempo esperando a alguien lo bastante pequeña para escuchar.",
        "Luna mira el sendero de casa. El sendero es liso y cálido, en la ventana de la cocina ya hay luz, y nadie se enteraría jamás.",
        "Los adultos dijeron que lo dejara en paz. El sendero es seguro. Pero el zumbido sigue ahí, fino y constante, pidiendo algo que Luna todavía no sabe nombrar.",
        "Se mete las manos en los bolsillos y da un paso lento hacia atrás. Luego otro, y otro más, lejos de la hierba alta y de la linterna apagada.",
        "En el desayuno no puede dejar de pensarlo. Prepara pan, una cuerda y la pequeña linterna de latón que su abuela le regaló el verano pasado.",
        "Se arrodilla en la hierba mojada y busca la linterna apagada. Se le resbalan los dedos en el metal frío y la linterna de latón rueda entre los helechos.",
        "Ahora hay dos linternas apagadas. Luna se sienta con las rodillas sucias y la mano ardiendo, y la tarde cae mucho más rápido de lo que esperaba.",
        "El claro se vuelve gris. Las doce linternas cálidas parecen lejanas, como ventanas de una casa en la que esta noche no puede entrar por mucho que llame.",
        "El frío sube desde el suelo hasta sus manos. Luna abraza sus rodillas, escucha el silencio completo y espera a que el gris siga su camino.",
        "Quizá la luz nunca fue para manos pequeñas. Quizá los adultos tenían razón, la linterna apagada simplemente está apagada, y ahí termina todo, sin nada más.",
        "Entonces Pip se acerca, tibio como un bolsillo. Pip es un espíritu de linterna, pequeño y brillante, y no discute nunca, solo se queda cerca. Sostén la luz, pequeña.",
        "Pip tararea otra vez las tres notas, y Luna por fin lo ve: su propia linterna nunca se apagó. Solo está entre los helechos, todavía brillando despacio.",
        "Luna la levanta y le quita las hojas. La linterna vacía es más grande de lo que creía, y la manera de llenarla no es la que esperaba.",
        "No se queda la luz para ella sola. Sostiene su linterna de latón sobre la linterna vacía y deja que la llamita se incline hacia el otro lado.",
        "Su propia linterna arde cada vez más bajo. El claro contiene el aliento. Entonces la linterna apagada responde con luz que corre por la hierba mojada.",
        "Una tras otra, las otras linternas se acercan. La luz cálida corre por las piedras, los charcos brillan como monedas y la tarde huele a resina y a pan.",
        "Sostén la luz, pequeña. Ahora lo dice todo el bosque, con doce voces pequeñas y una voz nueva que nunca había hablado antes y que suena como la suya.",
        "Los vecinos salen con pan caliente y manos tranquilas. Nadie dice la lección en voz alta, y aun así todos en el claro la entienden.",
        "Esa noche Luna vuelve a contar las linternas. Trece linternas brillan junto al sendero, y la hierba alta huele a lluvia, a musgo y a luz cálida.",
        "Antes de dormir deja la puerta un poco abierta, solo por si alguien pequeño viene esta noche buscando una luz propia, tal como hizo ella aquella tarde.",
    ],
}
