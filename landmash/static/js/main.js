$(document).ready(function(){

    // alert('hi');
    // var date = $('.todaysdate').text();

    var now = moment().format('dddd, MMMM DD' );

    $('.todaysdate').html(now);


});
