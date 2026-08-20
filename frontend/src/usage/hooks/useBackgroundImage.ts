import { useEffect, useState } from 'react';

const STORAGE_KEY = 'kb-usage-background-image';

interface UseBackgroundImageResult {
  backgroundImage: string;
  setBackgroundImage: (value: string) => void;
}

export function useBackgroundImage(): UseBackgroundImageResult {
  const [backgroundImage, setBackgroundImageState] = useState(() => localStorage.getItem(STORAGE_KEY) ?? '');

  useEffect(() => {
    if (backgroundImage) {
      localStorage.setItem(STORAGE_KEY, backgroundImage);
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, [backgroundImage]);

  return { backgroundImage, setBackgroundImage: setBackgroundImageState };
}
