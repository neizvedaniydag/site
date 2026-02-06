export const squat = {
    name: 'squat',
    title: 'Приседания',
    defaultReps: 15,
    
    instructions: [
        'Ноги на ширине плеч',
        'Опускайтесь до параллели бедер с полом',
        'Спина прямая, не наклоняйтесь',
        'Колени не выходят за носки',
        'Вернитесь в исходное положение'
    ],
    
    svgIcons: {
        bodyDown: '<svg width="56" height="56" viewBox="0 0 64 64" fill="white"><path d="M32 10 L32 40 M26 34 L32 40 L38 34" stroke="white" stroke-width="3" fill="none"/><rect x="28" y="42" width="8" height="3"/></svg>',
        bodyUp: '<svg width="56" height="56" viewBox="0 0 64 64" fill="white"><path d="M32 40 L32 10 M26 16 L32 10 L38 16" stroke="white" stroke-width="3" fill="none"/><rect x="28" y="8" width="8" height="3"/></svg>',
        bodyStraight: '<svg width="56" height="56" viewBox="0 0 64 64" fill="white"><rect x="20" y="28" width="24" height="4"/><circle cx="20" cy="30" r="3"/><circle cx="44" cy="30" r="3"/></svg>',
        check: '<svg width="48" height="48" viewBox="0 0 24 24" fill="white"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>'
    },
    
    thresholds: {
        kneeAngleDown: 90,      // Угол колена при приседе
        kneeAngleUp: 170,       // Угол колена при подъеме
        hipKneeOffset: 0.03,    // Разница высоты бедра и колена
        backAngleMin: 140       // Минимальный угол спины
    },
    
    getInitialState() {
        return { position: 'up' };
    },
    
    analyze(lm, state, showHint, logError, calcAngle) {
        const knee = (calcAngle(lm[23], lm[25], lm[27]) + calcAngle(lm[24], lm[26], lm[28])) / 2;
        const hipY = (lm[23].y + lm[24].y) / 2;
        const kneeY = (lm[25].y + lm[26].y) / 2;
        const backAngle = calcAngle(lm[11], lm[23], lm[25]);
        
        let result = { counted: false, correct: false, status: 'Готов' };
        
        if (knee < this.thresholds.kneeAngleDown && state.position === 'up') {
            state.position = 'down';
            result.counted = true;
            
            if (hipY > kneeY - this.thresholds.hipKneeOffset) {
                showHint('Приседайте ГЛУБЖЕ! Бедра параллельно полу', this.svgIcons.bodyDown);
                logError('Недостаточная глубина приседа');
                result.correct = false;
            } else if (backAngle < this.thresholds.backAngleMin) {
                showHint('Держите спину прямо!', this.svgIcons.bodyStraight);
                logError('Спина согнута');
                result.correct = false;
            } else {
                showHint('Отлично! Теперь встаньте', this.svgIcons.bodyUp, 'rgba(16, 185, 129, 0.95)');
                result.correct = true;
            }
            result.status = 'Присед';
        } else if (knee > this.thresholds.kneeAngleUp && state.position === 'down') {
            state.position = 'up';
            showHint('Готов к следующему приседу', this.svgIcons.bodyDown);
            result.status = 'Готов';
        }
        
        return result;
    }
};
