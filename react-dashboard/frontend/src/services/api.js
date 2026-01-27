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
