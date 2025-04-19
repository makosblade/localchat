import React from 'react';
import { getErrorMessage, getRequestId } from '../utils/errorHandler';

interface ErrorDisplayProps {
  error: unknown;
  retry?: () => void;
  className?: string;
}

/**
 * A component to display API errors with consistent styling and retry functionality
 */
const ErrorDisplay: React.FC<ErrorDisplayProps> = ({ error, retry, className = '' }) => {
  const errorMessage = getErrorMessage(error);
  const requestId = getRequestId(error);
  
  return (
    <div className={`bg-red-900/50 border border-red-700 rounded-lg p-4 my-2 ${className}`}>
      <div className="flex items-start">
        <div className="flex-shrink-0">
          <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
          </svg>
        </div>
        <div className="ml-3 flex-1">
          <h3 className="text-sm font-medium text-red-300">Error</h3>
          <div className="mt-1 text-sm text-red-200">
            <p>{errorMessage}</p>
            {requestId && (
              <p className="mt-1 text-xs text-red-400">
                If this issue persists, please contact support with Request ID: {requestId}
              </p>
            )}
          </div>
          {retry && (
            <div className="mt-3">
              <button
                type="button"
                onClick={retry}
                className="bg-red-800 hover:bg-red-700 text-white text-xs px-3 py-1 rounded-md"
              >
                Try Again
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

/**
 * A component to display model API specific errors with helpful suggestions
 */
export const ModelApiErrorDisplay: React.FC<ErrorDisplayProps> = (props) => {
  return (
    <div>
      <ErrorDisplay {...props} />
      <div className="bg-gray-800 rounded-lg p-4 mt-2 text-sm text-gray-300">
        <h4 className="font-medium text-gray-200">Troubleshooting Suggestions:</h4>
        <ul className="list-disc list-inside mt-1 space-y-1">
          <li>Verify the API URL in your profile is correct</li>
          <li>Check if the model name is valid for the selected API</li>
          <li>Ensure your API key has permission to access the model (if required)</li>
          <li>Try reducing the token size if the model has limitations</li>
        </ul>
      </div>
    </div>
  );
};

export default ErrorDisplay;
