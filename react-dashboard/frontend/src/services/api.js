import axios from 'axios';

const api = axios.create({
    baseURL: '/api',
});

export const getUsers = async (params) => {
    const { data } = await api.get('/users', { params });
    return data;
};

export const getUser = async (id) => {
    const { data } = await api.get(`/users/${id}`);
    return data;
};

export const getStats = async (params) => {
    const { data } = await api.get('/stats', { params });
    return data;
};

export const getFilters = async () => {
    const { data } = await api.get('/filters');
    return data;
};

export const getExclusions = async () => {
    const { data } = await api.get('/config/exclusion');
    return data;
};

export const addExclusion = async (email, exclude_charts, exclude_list) => {
    const { data } = await api.post('/config/exclusion', { email, exclude_charts, exclude_list });
    return data;
};

export const removeExclusion = async (email) => {
    const { data } = await api.delete('/config/exclusion', { params: { email } });
    return data;
};
