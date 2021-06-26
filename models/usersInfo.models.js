module.exports = (sequelize, Sequelize) => {
    let UsersInfo = sequelize.define("usersInfo", {
        phone_number: {
            type: Sequelize.STRING,
            allowNull: false,
        },
        name: {
            type: Sequelize.STRING,
            allowNull: false,
        },
        country_code: {
            type: Sequelize.STRING,
            allowNull: false,
        },
        full_phone_number: {
            type: Sequelize.STRING,
            allowNull: false,
            unique: true
        },
        iv: {
            type: Sequelize.STRING,
            allowNull: false,
        }
    });

    return UsersInfo;
}