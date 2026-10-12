import { isString, RAW_STRING, useStoredState } from '../../shared/useStoredState';

interface UseBackgroundImageResult {
  backgroundImage: string;
  setBackgroundImage: (value: string) => void;
}

// Stored as the raw path/URL string, not JSON-quoted; '' means no background.
export function useBackgroundImage(): UseBackgroundImageResult {
  const [backgroundImage, setBackgroundImage] = useStoredState('kb-usage-background-image', '', isString, RAW_STRING);
  return { backgroundImage, setBackgroundImage };
}
