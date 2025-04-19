import axios, { AxiosError } from 'axios';

export interface ApiErrorResponse {
  error: boolean;
  code: string;
  message: string;
  details?: any;
  request_id?: string;
}

/**
 * Extracts a user-friendly error message from an API error
 * 
 * @param error - The error object from axios or other source
 * @returns A formatted error message with details when available
 */
export const getErrorMessage = (error: unknown): string => {
  // Handle Axios errors
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ApiErrorResponse>;
    
    // If we have a response with our API error format
    if (axiosError.response?.data && 'error' in axiosError.response.data) {
      const errorData = axiosError.response.data;
      
      // Include request ID if available for support reference
      const requestIdInfo = errorData.request_id 
        ? ` (Request ID: ${errorData.request_id})` 
        : '';
      
      // Return formatted error message
      return `${errorData.message}${requestIdInfo}`;
    }
    
    // Handle standard HTTP errors
    if (axiosError.response) {
      return `Request failed with status ${axiosError.response.status}: ${axiosError.response.statusText}`;
    }
    
    // Handle network errors
    if (axiosError.request) {
      return 'Network error: Unable to connect to the server. Please check your internet connection.';
    }
  }
  
  // Handle non-Axios errors
  return error instanceof Error 
    ? error.message 
    : 'An unknown error occurred';
};

/**
 * Logs an error to the console with additional context
 * 
 * @param error - The error object
 * @param context - Additional context about where the error occurred
 */
export const logError = (error: unknown, context: string): void => {
  console.error(`Error in ${context}:`, error);
  
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ApiErrorResponse>;
    if (axiosError.response?.data) {
      console.error('API Error Details:', axiosError.response.data);
    }
  }
};

/**
 * Determines if an error is a specific type of API error
 * 
 * @param error - The error to check
 * @param errorCode - The API error code to check for
 * @returns True if the error matches the specified code
 */
export const isApiErrorCode = (error: unknown, errorCode: string): boolean => {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ApiErrorResponse>;
    return axiosError.response?.data?.code === errorCode;
  }
  return false;
};

/**
 * Determines if an error is related to model API issues
 * 
 * @param error - The error to check
 * @returns True if the error is related to model API
 */
export const isModelApiError = (error: unknown): boolean => {
  return isApiErrorCode(error, 'MODEL_API_ERROR');
};

/**
 * Determines if an error is related to database issues
 * 
 * @param error - The error to check
 * @returns True if the error is related to database
 */
export const isDatabaseError = (error: unknown): boolean => {
  return isApiErrorCode(error, 'DATABASE_ERROR');
};

/**
 * Gets the request ID from an API error if available
 * 
 * @param error - The error to extract the request ID from
 * @returns The request ID or undefined if not available
 */
export const getRequestId = (error: unknown): string | undefined => {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ApiErrorResponse>;
    return axiosError.response?.data?.request_id;
  }
  return undefined;
};
