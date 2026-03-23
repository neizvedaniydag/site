export const situp = {
    name: 'situp',
    title: 'Пресс (подъем корпуса)',
    defaultReps: 15,
    
    instructions: [
        'Лягте на спину, согните колени',
        'Стопы плотно прижаты к полу',
        'Руки за головой или на груди',
        'Поднимайте корпус к коленям',
        'Подбородок тянется к коленям',
        'Плавно опуститесь обратно'
    ],
    
    svgIcons: {
        bodyDown: '<svg width="56" height="56" viewBox="0 0 64 64" fill="white"><path d="M32 10 L32 40 M26 34 L32 40 L38 34" stroke="white" stroke-width="3" fill="none"/><rect x="28" y="42" width="8" height="3"/></svg>',
        bodyUp: '<svg width="56" height="56" viewBox="0 0 64 64" fill="white"><path d="M32 40 L32 10 M26 16 L32 10 L38 16" stroke="white" stroke-width="3" fill="none"/><rect x="28" y="8" width="8" height="3"/></svg>',
        torsoUp: '<svg width="56" height="56" viewBox="0 0 64 64" fill="white"><path d="M32 45 Q32 25 32 15" stroke="white" stroke-width="4" fill="none"/>ircle cx="32" cy="1212" r="5"/><path d="M20 35 L32 25 L44 35" stroke="white" stroke-width="3" fill="none"/></svg>',
        check: '<svg width="48" height="48" viewBox="0 0 24 24" fill="white"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>'
    },
    
    thresholds: {
        hipAngleUp: 90,         // Угол при подъеме
        hipAngleDown: 150,      // Угол при опускании
        hipAngleGood: 65        // Хороший угол подъема
    },
    
    getInitialState() {
        return { position: 'down' };
    },
    
    analyze(lm, state, showHint, logError, calcAngle) {
        const hipAngle = calcAngle(lm[11], lm[23], lm[25]);
        
        let result = { counted: false, correct: false, status: 'Готов' };
        
        if (hipAngle < this.thresholds.hipAngleUp && state.position === 'down') {
            state.position = 'up';
            result.counted = true;
            
            if (hipAngle > this.thresholds.hipAngleGood) {
                showHint('Поднимайтесь ВЫШЕ! Подбородок к коленям', this.svgIcons.bodyUp);
                logError('Недостаточная высота подъема корпуса');
                result.correct = false;
            } else {
                showHint('Отлично! Опуститесь обратно', this.svgIcons.bodyDown, 'rgba(16, 185, 129, 0.95)');
                result.correct = true;
            }
            result.status = 'Подъем';
        } else if (hipAngle > this.thresholds.hipAngleDown && state.position === 'up') {
            state.position = 'down';
            showHint('Готов к следующему', this.svgIcons.torsoUp);
            result.status = 'Готов';
        } else if (state.position === 'down') {
            result.status = 'Поднимайте корпус';
        } else {
            result.status = 'Опускайтесь';
        }
        
        return result;
    }
};
