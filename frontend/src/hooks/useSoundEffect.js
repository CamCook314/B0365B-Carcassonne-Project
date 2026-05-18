import { useCallback, useEffect, useRef } from 'react';

export const useSoundEffect = () => {
    const sounds = useRef({});
    

    useEffect(() => {
        const soundFiles = {
            gameStart    : '/sounds/game_start.ogg',
            placeTile    : '/sounds/place_tile.ogg',
            placeMeeple  : '/sounds/place_meeple.ogg',
            event1       : '/sounds/event1.ogg',
            event2       : '/sounds/event2.ogg',
            gameEnd      : '/sounds/game_end.ogg',
            score        : '/sounds/KSHMR Synth Shot 03 - (A).wav',
            changeTurn   : '/sounds/drum.ogg',
            detectedTile : '/sounds/KSHMR Synth Shot 10 - (C).wav'
        };

        // Preload sounds
        Object.entries(soundFiles).forEach(([key, url]) => {
            const audio = new Audio(url);
            audio.preload = 'auto';
            audio.volume = 0.5; 
            sounds.current[key] = audio;
        });
        
        // cleanup
        return () => {
            Object.values(sounds.current).forEach(audio => {
                audio.pause();
                audio.currentTime = 0;
            });
        };
    }, []);

    const play = useCallback((soundName, volume = 0.2) => {
        console.log(`Playing sound: ${soundName} at volume: ${volume}`);
        const sound = sounds.current[soundName];
        if (sound) {
            // clone to allow overlapping sounds
            const soundClone = sound.cloneNode();
            soundClone.volume = volume;
            soundClone.play();
        }
    }, []);

    return { play };
};